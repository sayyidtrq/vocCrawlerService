import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models import Competitor, Location, WorklistSyncState
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company
from app.integrations.onebox_worklist_client import OneBoxUnavailableError, OneBoxWorklistClient
from app.integrations.mock_review_client import MockReviewClient
from app.services.crawl_queue import CrawlQueue
from app.services.fetch_service import FetchService
from app.services.worklist_sync_service import (
    WorklistSyncError,
    WorklistSyncService,
    WorklistTenantMismatchError,
    is_onebox_managed,
)


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
        crawl_max_target_reviews=300,
        analysis_batch_size=3,
        prompt_version="v1",
        page_size=20,
        show_raw_payload=False,
    )


@pytest.fixture()
def company_id(session_factory):
    with session_factory() as session:
        company = Company(name="Test Company")
        session.add(company)
        session.commit()
        session.refresh(company)
        return company.id


class FakeWorklistClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def get_worklist(self):
        if self.error:
            raise self.error
        return self.payload


def onebox_settings(settings, company_id):
    return settings.model_copy(
        update={
            "onebox_base_url": "http://onebox.test",
            "onebox_service_email": "voc@test.invalid",
            "onebox_service_password": "secret",
            "onebox_site_id": 169,
            "onebox_company_id": company_id,
        }
    )


def payload():
    return {
        "meta": {"site_id": 169},
        "data": [
            {
                "kind": "location",
                "onebox_connection_id": 1039,
                "onebox_location_id": 1,
                "external_place_id": "place-new",
                "branch_name": "Hospital Baru",
                "hospital_name": "Test Hospital",
                "city": "Depok",
                "google_maps_url": "https://maps.example/place-new",
                "target_review_count": 25,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": True,
                "mock": True,
            },
            {
                "kind": "competitor",
                "onebox_connection_id": 1040,
                "onebox_location_id": 2,
                "external_place_id": "competitor-new",
                "branch_name": "Competitor Baru",
                "city": "Jakarta",
                "active": True,
                "crawl_enabled": False,
                "ingest_reviews": False,
            },
        ],
    }


def test_worklist_sync_upserts_and_soft_deactivates(session_factory, settings, company_id):
    with session_factory() as session:
        old = Location(
            company_id=company_id,
            hospital_name="Old",
            branch_name="Old Branch",
            source="onebox",
            external_place_id="place-old",
            onebox_connection_id=999,
            crawl_enabled=True,
            ingest_reviews=True,
            is_active=True,
        )
        session.add(old)
        session.commit()

    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload()),
    )
    result = service.refresh()

    assert result.status == "synced"
    assert result.fetched == 2
    assert result.upserted == 2
    assert result.deactivated == 1

    with session_factory() as session:
        location = session.scalar(
            select(Location).where(Location.external_place_id == "place-new")
        )
        competitor = session.scalar(
            select(Competitor).where(Competitor.external_place_id == "competitor-new")
        )
        old = session.scalar(
            select(Location).where(Location.external_place_id == "place-old")
        )
        assert location.branch_name == "Hospital Baru"
        assert location.onebox_connection_id == 1039
        assert location.is_mock is True
        assert competitor.crawl_enabled is False
        assert old.is_active is False
        assert old.crawl_enabled is False
        assert session.scalar(select(func.count(WorklistSyncState.id))) == 1


def test_worklist_sync_is_idempotent(session_factory, settings, company_id):
    client = FakeWorklistClient(payload())
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=client,
    )
    first = service.refresh()
    second = service.refresh()

    assert first.upserted == second.upserted == 2
    with session_factory() as session:
        assert session.scalar(select(func.count(Location.id))) == 1
        assert session.scalar(select(func.count(Competitor.id))) == 1


def test_worklist_outage_uses_last_successful_cache(session_factory, settings, company_id):
    cfg = onebox_settings(settings, company_id)
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=cfg,
        client=FakeWorklistClient(payload()),
    )
    service.refresh()

    outage = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=cfg,
        client=FakeWorklistClient(error=OneBoxUnavailableError("offline")),
    )
    result = outage.refresh()

    assert result.status == "cached"
    assert result.cache_age_seconds is not None
    assert "cached worklist" in result.warning

    with session_factory() as session:
        state = session.scalar(select(WorklistSyncState))
        assert state.last_error == "offline"


def test_worklist_requires_explicit_tenant(settings, session_factory):
    cfg = settings.model_copy(
        update={
            "onebox_base_url": "http://onebox.test",
            "onebox_service_email": "voc@test.invalid",
            "onebox_service_password": "secret",
            "onebox_site_id": 169,
            "onebox_company_id": None,
        }
    )
    service = WorklistSyncService(
        session_factory=session_factory,
        settings=cfg,
        client=FakeWorklistClient(payload()),
    )
    with pytest.raises(WorklistSyncError, match="ONEBOX_COMPANY_ID"):
        service.refresh()


def test_onebox_client_logs_in_once_and_reuses_jwt(settings, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/api/Authenticate":
            return httpx.Response(
                200,
                json={"token": "jwt-secret-value", "valid_until": "2099-01-01T00:00:00Z"},
            )
        return httpx.Response(200, json={"data": []})

    cfg = settings.model_copy(
        update={
            "onebox_base_url": "http://onebox.test",
            "onebox_service_email": "voc@test.invalid",
            "onebox_service_password": "secret",
            "onebox_site_id": 169,
        }
    )
    client = OneBoxWorklistClient(
        cfg,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.get_worklist()["data"] == []
    assert client.get_worklist()["data"] == []
    assert [request.url.path for request in calls].count("/api/Authenticate") == 1
    assert "jwt-secret-value" not in " ".join(str(request.headers) for request in calls)


def test_postman_mock_collection_matches_worklist_consumer(
    session_factory, settings, company_id
):
    collection_path = (
        Path(__file__).parents[1]
        / "postman"
        / "onebox-worklist-mock.postman_collection.json"
    )
    collection = json.loads(collection_path.read_text())
    responses = {
        "/" + "/".join(item["request"]["url"]["path"]): (
            item["response"][0]["code"],
            json.loads(item["response"][0]["body"]),
        )
        for item in collection["item"]
    }

    def handler(request):
        code, body = responses[request.url.path]
        return httpx.Response(code, json=body)

    cfg = onebox_settings(settings, company_id)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = WorklistSyncService(
            company_id=company_id,
            session_factory=session_factory,
            settings=cfg,
            client=OneBoxWorklistClient(cfg, http_client=http_client),
        ).refresh()

    assert result.status == "synced"
    assert result.fetched == result.upserted == 2


def ai_payload(location_extra):
    """One location row, with whatever AI keys the caller wants on it."""
    item = {
        "kind": "location",
        "onebox_connection_id": 2001,
        "onebox_location_id": 7,
        "external_place_id": "place-ai",
        "branch_name": "Hermina AI",
        "hospital_name": "Hermina",
        "city": "Depok",
        "target_review_count": 10,
        "active": True,
        "crawl_enabled": True,
        "ingest_reviews": True,
    }
    item.update(location_extra)
    return {"meta": {"site_id": 169}, "data": [item]}


def sync_once(session_factory, settings, company_id, payload_doc):
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload_doc),
    )
    assert service.refresh().status == "synced"
    with session_factory() as session:
        return session.scalar(
            select(Location).where(Location.external_place_id == "place-ai")
        )


def test_worklist_stores_the_ai_config_onebox_chose(
    session_factory, settings, company_id
):
    """OneBox owns the model choice, so it has to survive the sync.

    Before this contract the crawler parsed the worklist row and dropped these
    three keys, so the model OneBox picked never reached the code that calls
    the model. The regression was invisible from both sides: OneBox showed the
    setting saved, and the crawler kept analyzing with its env default.
    """
    location = sync_once(
        session_factory,
        settings,
        company_id,
        ai_payload(
            {
                "ai_enabled": False,
                "ai_model": "llama3.2-1b",
                "ai_output_schema_version": "v1",
            }
        ),
    )

    assert location.ai_enabled is False
    assert location.ai_model == "llama3.2-1b"
    assert location.ai_output_schema_version == "v1"


def test_worklist_without_ai_keys_leaves_analysis_enabled(
    session_factory, settings, company_id
):
    """A worklist row predating the contract must not disable analysis.

    The worklist is served by a OneBox that can be older than this crawler.
    Reading a missing key as False would stop analysis for every branch during
    a deploy window, with no configuration change behind it to explain it.
    """
    location = sync_once(session_factory, settings, company_id, ai_payload({}))

    assert location.ai_enabled is True
    assert location.ai_model is None
    assert location.ai_output_schema_version is None


def test_worklist_treats_a_blank_model_as_no_choice(
    session_factory, settings, company_id
):
    """"" and null both mean "operator did not pick", and must store alike.

    OneBox sends null, but a hand-edited Connection.Options row reaches the
    worklist carrying an empty string for the same intent. Storing the two
    differently would leave the model fallback with two cases to handle
    forever, and the empty one would read as a model with a blank name.
    """
    location = sync_once(
        session_factory,
        settings,
        company_id,
        ai_payload({"ai_model": "   ", "ai_output_schema_version": ""}),
    )

    assert location.ai_model is None
    assert location.ai_output_schema_version is None


def test_worklist_sync_persists_onebox_target_id_for_location_and_competitor(
    session_factory, settings, company_id
):
    payload_doc = {
        "meta": {"site_id": 169},
        "data": [
            {
                "kind": "location",
                "onebox_connection_id": 1001,
                "onebox_location_id": 11,
                "onebox_target_id": 888,
                "external_place_id": "place-loc-888",
                "branch_name": "Hospital 888",
                "hospital_name": "Hermina",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": True,
            },
            {
                "kind": "competitor",
                "onebox_connection_id": 1002,
                "onebox_target_id": 999,
                "external_place_id": "place-comp-999",
                "name": "Competitor 999",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": False,
            },
        ],
    }
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload_doc),
    )
    result = service.refresh()
    assert result.status == "synced"
    with session_factory() as session:
        loc = session.scalar(
            select(Location).where(Location.external_place_id == "place-loc-888")
        )
        comp = session.scalar(
            select(Competitor).where(Competitor.external_place_id == "place-comp-999")
        )
        assert loc.onebox_target_id == 888
        assert comp.onebox_target_id == 999


def test_worklist_sync_absent_target_id_persists_as_none(
    session_factory, settings, company_id
):
    payload_doc = {
        "meta": {"site_id": 169},
        "data": [
            {
                "kind": "location",
                "onebox_connection_id": 1001,
                "onebox_location_id": 11,
                "external_place_id": "place-loc-none",
                "branch_name": "Hospital None",
                "hospital_name": "Hermina",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": True,
            },
            {
                "kind": "competitor",
                "onebox_connection_id": 1002,
                "external_place_id": "place-comp-none",
                "name": "Competitor None",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": False,
            },
        ],
    }
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload_doc),
    )
    result = service.refresh()
    assert result.status == "synced"
    with session_factory() as session:
        loc = session.scalar(
            select(Location).where(Location.external_place_id == "place-loc-none")
        )
        comp = session.scalar(
            select(Competitor).where(Competitor.external_place_id == "place-comp-none")
        )
        assert loc.onebox_target_id is None
        assert comp.onebox_target_id is None


def test_worklist_sync_non_integer_target_id_raises_error(
    session_factory, settings, company_id
):
    payload_doc = {
        "meta": {"site_id": 169},
        "data": [
            {
                "kind": "location",
                "onebox_connection_id": 1001,
                "onebox_location_id": 11,
                "onebox_target_id": "not_an_int",
                "external_place_id": "place-loc-invalid",
                "branch_name": "Hospital Invalid",
                "hospital_name": "Hermina",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": True,
            }
        ],
    }
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload_doc),
    )
    with pytest.raises(WorklistSyncError, match="onebox_target_id must be an integer"):
        service.refresh()


def test_worklist_sync_duplicate_target_id_raises_error(
    session_factory, settings, company_id
):
    payload_doc = {
        "meta": {"site_id": 169},
        "data": [
            {
                "kind": "location",
                "onebox_connection_id": 1001,
                "onebox_location_id": 11,
                "onebox_target_id": 555,
                "external_place_id": "place-loc-dup",
                "branch_name": "Hospital Dup",
                "hospital_name": "Hermina",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": True,
            },
            {
                "kind": "competitor",
                "onebox_connection_id": 1002,
                "onebox_target_id": 555,
                "external_place_id": "place-comp-dup",
                "name": "Competitor Dup",
                "city": "Jakarta",
                "target_review_count": 10,
                "active": True,
                "crawl_enabled": True,
                "ingest_reviews": False,
            },
        ],
    }
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload_doc),
    )
    with pytest.raises(WorklistSyncError, match="Duplicate onebox_target_id: 555"):
        service.refresh()


def test_worklist_sync_deactivates_managed_target_id_only_row_when_disappeared(
    session_factory, settings, company_id
):
    with session_factory() as session:
        managed_loc = Location(
            company_id=company_id,
            hospital_name="Hermina",
            branch_name="Hermina Target Only",
            source="apify_google_maps",
            external_place_id="place-target-only",
            onebox_connection_id=None,
            onebox_location_id=None,
            onebox_target_id=777,
            crawl_enabled=True,
            ingest_reviews=True,
            is_active=True,
        )
        manual_loc = Location(
            company_id=company_id,
            hospital_name="Hermina",
            branch_name="Hermina Manual",
            source="manual",
            external_place_id="place-manual",
            onebox_connection_id=None,
            onebox_location_id=None,
            onebox_target_id=None,
            crawl_enabled=True,
            ingest_reviews=True,
            is_active=True,
        )
        session.add_all([managed_loc, manual_loc])
        session.commit()

    empty_payload = {"meta": {"site_id": 169}, "data": []}
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(empty_payload),
    )
    service.refresh()

    with session_factory() as session:
        ml = session.scalar(
            select(Location).where(Location.external_place_id == "place-target-only")
        )
        man = session.scalar(
            select(Location).where(Location.external_place_id == "place-manual")
        )
        assert ml.is_active is False
        assert man.is_active is True


def test_is_onebox_managed_unit():
    class DummyTarget:
        def __init__(self, conn=None, loc=None, target=None):
            self.onebox_connection_id = conn
            self.onebox_location_id = loc
            self.onebox_target_id = target

    assert is_onebox_managed(DummyTarget(target=123)) is True
    assert is_onebox_managed(DummyTarget(conn=456)) is True
    assert is_onebox_managed(DummyTarget(loc=789)) is True
    assert is_onebox_managed(DummyTarget()) is False
    assert is_onebox_managed(object()) is False
    assert is_onebox_managed(None) is False


def test_fetch_location_skipped_disabled_for_target_id_only_row(
    session_factory, settings, company_id
):
    from app.services.fetch_service import FetchService

    with session_factory() as session:
        location = Location(
            company_id=company_id,
            hospital_name="Hermina",
            branch_name="Hermina Disabled",
            source="mock",
            external_place_id="place-disabled-target",
            onebox_connection_id=None,
            onebox_location_id=None,
            onebox_target_id=888,
            crawl_enabled=False,
            ingest_reviews=True,
            is_active=True,
        )
        session.add(location)
        session.commit()
        session.refresh(location)
        loc_id = location.id

    service = FetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
    )
    result = service.fetch_location(loc_id)
    assert result["status"] == "skipped_disabled"
    assert "disabled by the OneBox worklist" in result["error_message"]



def test_worklist_generated_by_onebox_registry_mode_syncs_and_survives_cutover(
    session_factory, settings, company_id
):
    """Payload gerado kode OneBox (VocWorklist::fromTarget) diproses apa adanya."""
    import copy

    registry = json.loads(
        (Path(__file__).parent / "fixtures" / "onebox_registry_worklist.json").read_text()
    )
    client = FakeWorklistClient(payload=registry)
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=client,
    )

    result = service.refresh()
    assert result.upserted == 3 and result.deactivated == 0
    with session_factory() as session:
        depok = session.scalar(
            select(Location).where(Location.external_place_id == "ChIJ-depok-0001")
        )
        competitor = session.scalar(
            select(Competitor).where(Competitor.external_place_id == "ChIJ-comp-0002")
        )
        assert (depok.onebox_target_id, depok.onebox_location_id) == (501, 12)
        assert depok.ai_model == "jev-1" and depok.ingest_reviews is True
        assert competitor.onebox_target_id == 502
        assert competitor.crawl_enabled is False and competitor.ingest_reviews is False
        depok_id = depok.id

    # Cutover: OneBox berhenti mengirim id koneksi lama. Baris tetap dikelola
    # (penanda berpindah ke id lokasi/target) dan tidak diduplikasi.
    cutover = copy.deepcopy(registry)
    for item in cutover["data"]:
        item["onebox_connection_id"] = None
    client.payload = cutover
    assert service.refresh().deactivated == 0
    with session_factory() as session:
        depok = session.scalar(
            select(Location).where(Location.external_place_id == "ChIJ-depok-0001")
        )
        assert depok.id == depok_id and depok.onebox_connection_id is None
        assert session.scalar(select(func.count()).select_from(Location)) == 2

    # Target yang hilang dari worklist harus tetap dinonaktifkan walau tanpa id koneksi.
    cutover["data"] = [
        item for item in cutover["data"] if item["external_place_id"] != "ChIJ-depok-0001"
    ]
    assert service.refresh().deactivated == 1
    with session_factory() as session:
        depok = session.scalar(
            select(Location).where(Location.external_place_id == "ChIJ-depok-0001")
        )
        assert depok.is_active is False and depok.crawl_enabled is False


# --- MT-02: refresh on-demand tidak boleh melintasi tenant -------------------
#
# Worklist yang ditarik selalu milik site di konfigurasi (ONEBOX_SITE_ID), dan
# company pemiliknya ONEBOX_COMPANY_ID. Company lain yang memicu refresh
# (enqueue target tak dikenal, analisa lokasi tak dikenal, fetch) tidak boleh
# menerima worklist itu, apalagi kehilangan targetnya sendiri.


class RecordingWorklistClient(FakeWorklistClient):
    def __init__(self, payload=None, error=None):
        super().__init__(payload, error)
        self.calls = 0

    def get_worklist(self):
        self.calls += 1
        return super().get_worklist()


def _other_company_with_managed_location(session_factory):
    with session_factory() as session:
        other = Company(name="Other Tenant")
        session.add(other)
        session.flush()
        session.add(
            Location(
                company_id=other.id,
                hospital_name="Other Org",
                branch_name="Other Branch",
                source="onebox",
                external_place_id="place-other",
                onebox_connection_id=77,
                crawl_enabled=True,
                ingest_reviews=True,
                is_active=True,
            )
        )
        session.commit()
        return other.id


def _other_company_state(session_factory, other_id):
    with session_factory() as session:
        locations = session.scalars(select(Location).where(Location.company_id == other_id)).all()
        states = session.scalars(
            select(WorklistSyncState).where(WorklistSyncState.company_id == other_id)
        ).all()
        return locations, states


def test_refresh_refuses_a_company_that_does_not_own_the_configured_site(
    session_factory, settings, company_id
):
    other_id = _other_company_with_managed_location(session_factory)
    client = RecordingWorklistClient(payload())
    service = WorklistSyncService(
        company_id=other_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=client,
    )

    with pytest.raises(WorklistTenantMismatchError):
        service.refresh()

    assert client.calls == 0
    locations, states = _other_company_state(session_factory, other_id)
    assert [(row.external_place_id, row.is_active, row.crawl_enabled) for row in locations] == [
        ("place-other", True, True)
    ]
    assert states == []
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Competitor)) == 0


def test_tenant_mismatch_is_a_worklist_sync_error():
    assert issubclass(WorklistTenantMismatchError, WorklistSyncError)


def test_enqueue_auto_refresh_never_touches_a_foreign_company(
    session_factory, settings, company_id, monkeypatch
):
    other_id = _other_company_with_managed_location(session_factory)
    client = RecordingWorklistClient(payload())
    monkeypatch.setattr(
        "app.services.worklist_sync_service.OneBoxWorklistClient", lambda _settings: client
    )
    queue = CrawlQueue(
        session_factory=session_factory, settings=onebox_settings(settings, company_id)
    )

    assert queue._refresh_worklist_once(other_id, [123]) is False

    assert client.calls == 0
    locations, states = _other_company_state(session_factory, other_id)
    assert [row.is_active for row in locations] == [True]
    assert states == []


def test_fetch_skips_the_refresh_for_a_foreign_company_instead_of_failing(
    session_factory, settings, company_id
):
    other_id = _other_company_with_managed_location(session_factory)
    client = RecordingWorklistClient(payload())
    fetch = FetchService(
        company_id=other_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=MockReviewClient(),
    )
    fetch.worklist_sync_service.client = client

    result = fetch._refresh_worklist()

    assert result["status"] == "skipped_foreign_tenant"
    assert client.calls == 0
    locations, _ = _other_company_state(session_factory, other_id)
    assert [row.is_active for row in locations] == [True]


def test_owner_company_still_refreshes_normally(session_factory, settings, company_id):
    client = RecordingWorklistClient(payload())
    result = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=client,
    ).refresh()

    assert client.calls == 1
    assert result.status == "synced"
