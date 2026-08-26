import json
from dataclasses import replace
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
from app.services.worklist_sync_service import WorklistSyncError, WorklistSyncService


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
    return replace(
        settings,
        onebox_base_url="http://onebox.test",
        onebox_service_email="voc@test.invalid",
        onebox_service_password="secret",
        onebox_site_id=169,
        onebox_company_id=company_id,
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
    cfg = replace(
        settings,
        onebox_base_url="http://onebox.test",
        onebox_service_email="voc@test.invalid",
        onebox_service_password="secret",
        onebox_site_id=169,
        onebox_company_id=None,
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

    cfg = replace(
        settings,
        onebox_base_url="http://onebox.test",
        onebox_service_email="voc@test.invalid",
        onebox_service_password="secret",
        onebox_site_id=169,
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
