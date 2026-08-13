"""Delta-sync matrix for the OneBox integration pull (VOC-CS-02).

The property under test throughout is: across a full pull cycle, OneBox sees every
review exactly once — no gaps, no duplicates — even while rows are being written
underneath it. Every failure mode here is silent in production: a skipped review
never raises, it simply never reaches OneBox, so these tests are the only thing
standing between a keyset bug and permanently missing tickets.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Company, Location, Review, ReviewAnalysis
from app.integrations.mock_gemini_client import MockGeminiClient
from app.services.analysis_service import AnalysisService
from app.utils.integration_cursor import (
    CURSOR_VERSION,
    CursorPosition,
    IntegrationCursor,
    encode_cursor,
)
from apps.api.app_api.routers.integration_reviews import (
    ServicePrincipal,
    get_integration_session_factory,
    require_service_principal,
)
from apps.api.main import create_app

BASE = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
ENDPOINT = "/api/integration/v1/reviews"


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        app_env="test",
        app_name="Review System",
        log_level="INFO",
        export_dir=tmp_path / "exports",
        database_url="sqlite+pysqlite:///:memory:",
        cors_allowed_origins=("http://localhost:3000",),
        review_source_mode="mock",
        google_maps_api_key=None,
        google_places_language_code="id",
        google_places_region_code="ID",
        local_llm_base_url="http://localhost:11434/v1/",
        local_llm_api_key="test",
        local_llm_model="mock",
        fetch_limit_per_location=50,
        fetch_timeout_seconds=1,
        fetch_max_retry=0,
        selenium_headless=True,
        selenium_default_target_reviews=100,
        selenium_max_target_reviews=300,
        selenium_scroll_delay_seconds=2,
        selenium_max_scroll_attempts=100,
        selenium_wait_timeout_seconds=20,
        selenium_user_data_dir=None,
        analysis_batch_size=10,
        prompt_version="v1",
        page_size=20,
        show_raw_payload=False,
    )


@pytest.fixture()
def tenants(session_factory):
    """Two companies, each with one location. The second exists to prove isolation."""
    with session_factory() as session:
        primary = Company(name="Hermina", ai_enable_flag=True, total_enable_review=500)
        other = Company(name="Rival", ai_enable_flag=True, total_enable_review=500)
        session.add_all([primary, other])
        session.commit()

        depok = Location(
            company_id=primary.id,
            hospital_name="Hermina",
            branch_name="Cabang Depok",
            source="selenium_google_maps",
            external_place_id="place-depok",
        )
        bekasi = Location(
            company_id=primary.id,
            hospital_name="Hermina",
            branch_name="Cabang Bekasi",
            source="selenium_google_maps",
            external_place_id="place-bekasi",
        )
        rival = Location(
            company_id=other.id,
            hospital_name="Rival",
            branch_name="Rival Branch",
            source="selenium_google_maps",
            external_place_id="place-rival",
        )
        session.add_all([depok, bekasi, rival])
        session.commit()

        return {
            "company_id": primary.id,
            "other_company_id": other.id,
            "depok_id": depok.id,
            "bekasi_id": bekasi.id,
            "rival_location_id": rival.id,
        }


def add_review(session_factory, *, company_id, location_id, tag, sync_at, text="ok"):
    with session_factory() as session:
        review = Review(
            company_id=company_id,
            location_id=location_id,
            source="selenium_google_maps",
            external_place_id="place-x",
            external_review_id=tag,
            reviewer_name="Customer",
            rating=4,
            review_text=text,
            review_time=sync_at,
            review_hash=f"hash-{tag}",
            created_at=sync_at,
            updated_at=sync_at,
            sync_updated_at=sync_at,
        )
        session.add(review)
        session.commit()
        return review.id


def make_client(session_factory, company_id) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_integration_session_factory] = lambda: session_factory
    app.dependency_overrides[require_service_principal] = lambda: ServicePrincipal(
        client_id=1,
        key_id="voc_test_key",
        company_id=company_id,
        scopes=frozenset({"reviews:read"}),
    )
    return TestClient(app)


@pytest.fixture()
def client(session_factory, tenants):
    return make_client(session_factory, tenants["company_id"])


def get_page(client, **params):
    response = client.get(ENDPOINT, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def drain(client, limit, **params):
    """Run a full cycle to exhaustion. Returns (ids in order, final checkpoint)."""
    collected: list[int] = []
    cursor = None
    for _ in range(50):  # bounded: a cursor that never terminates must fail loudly
        page_params = {"limit": limit, **params} if cursor is None else {"limit": limit, "cursor": cursor}
        payload = get_page(client, **page_params)
        collected.extend(item["id"] for item in payload["data"])
        if not payload["page"]["has_more"]:
            return collected, payload["page"]["checkpoint_cursor"]
        cursor = payload["page"]["next_cursor"]
        assert cursor, "has_more=true must carry a next_cursor"
    raise AssertionError("cycle did not terminate — cursor is not advancing")


# --------------------------------------------------------------------------- #
# Paging integrity
# --------------------------------------------------------------------------- #


def test_multi_page_pull_sees_every_review_exactly_once(client, session_factory, tenants):
    expected = [
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"r{i}",
            sync_at=BASE + timedelta(minutes=i),
        )
        for i in range(10)
    ]

    collected, checkpoint = drain(client, limit=3)

    assert collected == expected  # order, no gaps, no duplicates
    assert len(set(collected)) == 10
    assert checkpoint


def test_rows_sharing_a_timestamp_are_not_skipped_or_duplicated(
    client, session_factory, tenants
):
    """The id tie-break earns its keep here.

    A batch commits with one timestamp, so a page boundary lands inside the tie.
    Ordering on the timestamp alone would make that boundary arbitrary and lose or
    repeat rows across pages.
    """
    same_instant = BASE + timedelta(hours=5)
    expected = [
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"tie{i}",
            sync_at=same_instant,
        )
        for i in range(5)
    ]

    collected, _ = drain(client, limit=2)

    assert collected == expected
    assert len(set(collected)) == 5


def test_page_size_one(client, session_factory, tenants):
    expected = [
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"one{i}",
            sync_at=BASE + timedelta(minutes=i),
        )
        for i in range(4)
    ]

    collected, _ = drain(client, limit=1)

    assert collected == expected


def test_empty_tenant_returns_empty_page_and_a_resumable_checkpoint(client):
    payload = get_page(client, limit=10)

    assert payload["data"] == []
    assert payload["page"]["has_more"] is False
    assert payload["page"]["next_cursor"] is None
    # Still resumable: the consumer stores this and picks up whatever arrives next.
    assert payload["page"]["checkpoint_cursor"]


def test_updated_since_bootstraps_the_lower_bound(client, session_factory, tenants):
    old = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="old",
        sync_at=BASE,
    )
    recent = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="recent",
        sync_at=BASE + timedelta(days=10),
    )

    payload = get_page(client, limit=10, updated_since="2026-07-05T00:00:00Z")
    ids = [item["id"] for item in payload["data"]]

    assert recent in ids
    assert old not in ids


# --------------------------------------------------------------------------- #
# Snapshot isolation
# --------------------------------------------------------------------------- #


def test_row_written_mid_cycle_does_not_join_the_open_snapshot(
    client, session_factory, tenants
):
    """The upper bound is frozen when the cycle opens.

    Without it, a row landing between two pages shifts the window under the
    consumer and the row at the old boundary is silently skipped.
    """
    for i in range(4):
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"snap{i}",
            sync_at=BASE + timedelta(minutes=i),
        )

    first = get_page(client, limit=2)
    assert first["page"]["has_more"] is True

    # Lands after the snapshot opened, carrying the newest watermark of all.
    intruder = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="intruder",
        sync_at=BASE + timedelta(hours=1),
    )

    second = get_page(client, limit=2, cursor=first["page"]["next_cursor"])
    seen_this_cycle = [item["id"] for item in first["data"]] + [
        item["id"] for item in second["data"]
    ]

    assert second["page"]["has_more"] is False
    assert intruder not in seen_this_cycle
    assert len(seen_this_cycle) == 4

    # It is not lost — the next cycle, resumed from this checkpoint, delivers it.
    next_cycle = get_page(client, cursor=second["page"]["checkpoint_cursor"], limit=10)
    assert [item["id"] for item in next_cycle["data"]] == [intruder]


def test_idle_next_cycle_returns_nothing(client, session_factory, tenants):
    add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="only",
        sync_at=BASE,
    )

    _, checkpoint = drain(client, limit=10)
    payload = get_page(client, cursor=checkpoint, limit=10)

    assert payload["data"] == []
    assert payload["page"]["has_more"] is False
    assert payload["page"]["checkpoint_cursor"]


# --------------------------------------------------------------------------- #
# Late analysis — the reason sync_updated_at exists at all
# --------------------------------------------------------------------------- #


def parse_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def analysis_service(session_factory, company_id, settings) -> AnalysisService:
    return AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=MockGeminiClient(),
    )


def test_analysis_completed_after_a_pull_resurfaces_the_review(
    client, session_factory, tenants, settings
):
    """The failure this whole design exists to prevent.

    Analysis is append-only. Before the watermark existed, a review analysed after
    it had already been pulled stayed below the consumer's checkpoint forever, and
    OneBox never learned it had been analysed at all — no error, just a ticket that
    never appeared.
    """
    review_id = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="late",
        sync_at=BASE,
        text="Antrean IGD lama sekali",
    )

    first_cycle, checkpoint = drain(client, limit=10)
    assert first_cycle == [review_id]
    assert first_cycle and get_page(client, cursor=checkpoint, limit=10)["data"] == []

    analysis_service(session_factory, tenants["company_id"], settings).analyze_pending()

    returned = get_page(client, cursor=checkpoint, limit=10)["data"]

    assert [item["id"] for item in returned] == [review_id]
    assert returned[0]["analyzed"] is True
    assert returned[0]["analysis_status"] == "completed"
    assert returned[0]["sentiment"]
    # The watermark advanced past the checkpoint the consumer had already stored —
    # that advance is the only reason this row came back.
    assert parse_z(returned[0]["sync_updated_at"]) > BASE


def test_rerunning_analysis_moves_the_watermark_again(
    client, session_factory, tenants, settings
):
    review_id = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="rerun",
        sync_at=BASE,
        text="Pelayanan lambat",
    )
    service = analysis_service(session_factory, tenants["company_id"], settings)

    service.analyze_pending()
    _, checkpoint = drain(client, limit=10)
    assert get_page(client, cursor=checkpoint, limit=10)["data"] == []

    service.rerun_review(review_id)  # append-only: a second analysis row

    payload = get_page(client, cursor=checkpoint, limit=10)
    assert [item["id"] for item in payload["data"]] == [review_id]

    with session_factory() as session:
        rows = session.scalars(
            select(ReviewAnalysis).where(ReviewAnalysis.review_id == review_id)
        ).all()
    assert len(rows) == 2  # append-only preserved
    # The consumer is handed the newest analysis, not the stale first one.
    assert payload["data"][0]["analyzed"] is True


def test_failed_analysis_moves_the_watermark_and_syncs_status(
    client, session_factory, tenants, settings
):
    review_id = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="failed-analysis",
        sync_at=BASE,
        text="Pelayanan lambat",
    )
    _, checkpoint = drain(client, limit=10)

    class FailingClient:
        model_name = "failing-test"

        def __init__(self):
            self.last_usage = {}

        def analyze_review(self, review):
            raise RuntimeError("provider detail must stay in server logs")

    result = AnalysisService(
        company_id=tenants["company_id"],
        session_factory=session_factory,
        settings=settings,
        client=FailingClient(),
    ).rerun_review(review_id)
    payload = get_page(client, cursor=checkpoint, limit=10)

    assert result["errors"] == [{"review_id": review_id, "error": "Analysis failed."}]
    assert [item["id"] for item in payload["data"]] == [review_id]
    assert payload["data"][0]["analysis_status"] == "failed"
    assert payload["data"][0]["analyzed"] is False
    assert parse_z(payload["data"][0]["sync_updated_at"]) > BASE


# --------------------------------------------------------------------------- #
# Cursor security
# --------------------------------------------------------------------------- #


def test_tampered_cursor_is_rejected(client, session_factory, tenants):
    for i in range(3):
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"t{i}",
            sync_at=BASE + timedelta(minutes=i),
        )
    cursor = get_page(client, limit=1)["page"]["next_cursor"]

    # Flip the payload while keeping the shape: signature must catch it.
    payload_part, signature_part = cursor.split(".", 1)
    forged = f"{payload_part[:-4]}AAAA.{signature_part}"

    response = client.get(ENDPOINT, params={"cursor": forged})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_unsigned_cursor_is_rejected(client):
    response = client.get(ENDPOINT, params={"cursor": "just-some-string"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_cursor_issued_to_another_tenant_is_rejected(session_factory, tenants):
    """A validly signed cursor still may not be replayed across tenants."""
    add_review(
        session_factory,
        company_id=tenants["other_company_id"],
        location_id=tenants["rival_location_id"],
        tag="rival-1",
        sync_at=BASE,
    )
    add_review(
        session_factory,
        company_id=tenants["other_company_id"],
        location_id=tenants["rival_location_id"],
        tag="rival-2",
        sync_at=BASE + timedelta(minutes=1),
    )

    rival_client = make_client(session_factory, tenants["other_company_id"])
    rival_cursor = get_page(rival_client, limit=1)["page"]["next_cursor"]
    assert rival_cursor

    primary_client = make_client(session_factory, tenants["company_id"])
    response = primary_client.get(ENDPOINT, params={"cursor": rival_cursor})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_changing_location_id_mid_cycle_is_rejected(client, session_factory, tenants):
    for i in range(3):
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"f{i}",
            sync_at=BASE + timedelta(minutes=i),
        )

    cursor = get_page(client, limit=1, location_id=tenants["depok_id"])["page"][
        "next_cursor"
    ]
    response = client.get(
        ENDPOINT, params={"cursor": cursor, "location_id": tenants["bekasi_id"]}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR_CONTEXT"


def test_cursor_alone_keeps_the_location_filter(client, session_factory, tenants):
    """A follow-up page sends only the cursor, per the contract.

    The filter has to survive inside it — if it silently widened to the whole
    tenant here, the other location's rows would be pulled into a cycle that was
    never meant to include them.
    """
    depok = [
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"d{i}",
            sync_at=BASE + timedelta(minutes=i),
        )
        for i in range(3)
    ]
    bekasi = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["bekasi_id"],
        tag="other-branch",
        sync_at=BASE + timedelta(minutes=1),
    )

    first = get_page(client, limit=1, location_id=tenants["depok_id"])
    # Note: no location_id on the follow-up request.
    second = get_page(client, limit=10, cursor=first["page"]["next_cursor"])

    seen = [item["id"] for item in first["data"]] + [
        item["id"] for item in second["data"]
    ]
    assert seen == depok
    assert bekasi not in seen


def test_cursor_combined_with_updated_since_is_rejected(client, session_factory, tenants):
    for i in range(3):
        add_review(
            session_factory,
            company_id=tenants["company_id"],
            location_id=tenants["depok_id"],
            tag=f"u{i}",
            sync_at=BASE + timedelta(minutes=i),
        )
    cursor = get_page(client, limit=1)["page"]["next_cursor"]

    response = client.get(
        ENDPOINT, params={"cursor": cursor, "updated_since": "2026-07-01T00:00:00Z"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR_CONTEXT"


def test_expired_cursor_is_rejected(client, session_factory, tenants):
    add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="stale",
        sync_at=BASE,
    )
    stale = encode_cursor(
        IntegrationCursor(
            version=CURSOR_VERSION,
            company_id=tenants["company_id"],
            location_id=None,
            lower=CursorPosition(BASE, 0),
            upper=CursorPosition(BASE, 999),
            issued_at=datetime.now(timezone.utc) - timedelta(days=31),
        ),
        # The same secret the running app signs with, so this cursor is genuinely
        # valid and only its age can be what rejects it.
        get_settings().integration_cursor_secret,
    )

    response = client.get(ENDPOINT, params={"cursor": stale})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_location_filter_scopes_the_cycle(client, session_factory, tenants):
    depok = add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["depok_id"],
        tag="in-depok",
        sync_at=BASE,
    )
    add_review(
        session_factory,
        company_id=tenants["company_id"],
        location_id=tenants["bekasi_id"],
        tag="in-bekasi",
        sync_at=BASE + timedelta(minutes=1),
    )

    collected, _ = drain(client, limit=1, location_id=tenants["depok_id"])
    assert collected == [depok]
