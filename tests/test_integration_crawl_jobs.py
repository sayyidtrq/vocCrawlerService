from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.models import ApiClient, Company, CrawlBatch, CrawlJob, Location
from app.services.crawl_job_service import CrawlJobService
from apps.api.app_api.routers.integration_crawl_jobs import (
    get_crawl_queue_session_factory,
)
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        company_a = Company(name="Tenant A")
        company_b = Company(name="Tenant B")
        session.add_all([company_a, company_b])
        session.flush()
        client_a = ApiClient(
            company_id=company_a.id,
            name="onebox-a",
            key_id="key-a",
            secret_hash="hash-a",
            scopes=["crawl:enqueue", "crawl:read"],
        )
        client_b = ApiClient(
            company_id=company_b.id,
            name="onebox-b",
            key_id="key-b",
            secret_hash="hash-b",
            scopes=["crawl:enqueue", "crawl:read"],
        )
        session.add_all([client_a, client_b])
        session.flush()
        session.add_all(
            [
                Location(
                    company_id=company_a.id,
                    hospital_name="Hospital A",
                    branch_name="Branch A",
                    source="selenium_google_maps",
                    external_place_id="place-a",
                    onebox_location_id=101,
                    target_review_count=2,
                    crawl_enabled=True,
                    ingest_reviews=True,
                    is_active=True,
                ),
                Location(
                    company_id=company_a.id,
                    hospital_name="Hospital A",
                    branch_name="Branch A2",
                    source="selenium_google_maps",
                    external_place_id="place-a2",
                    onebox_location_id=102,
                    target_review_count=2,
                    crawl_enabled=True,
                    ingest_reviews=True,
                    is_active=True,
                ),
                Location(
                    company_id=company_b.id,
                    hospital_name="Hospital B",
                    branch_name="Branch B",
                    source="selenium_google_maps",
                    external_place_id="place-b",
                    onebox_location_id=201,
                    target_review_count=2,
                    crawl_enabled=True,
                    ingest_reviews=True,
                    is_active=True,
                ),
            ]
        )
        session.commit()
    return factory


def principal(company_id: int, client_id: int, scopes=None) -> ServicePrincipal:
    return ServicePrincipal(
        client_id=client_id,
        key_id=f"key-{company_id}",
        company_id=company_id,
        scopes=frozenset(scopes or ["crawl:enqueue", "crawl:read"]),
    )


def make_client(session_factory, current_principal: ServicePrincipal) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_crawl_queue_session_factory] = lambda: (
        session_factory
    )
    application.dependency_overrides[require_service_principal] = lambda: (
        current_principal
    )
    return TestClient(application)


def enqueue(
    client: TestClient,
    location_id: int = 101,
    key: str = "169:2026-07-29:morning",
    target_review_count: int | None = None,
):
    target = {"onebox_location_id": location_id}
    if target_review_count is not None:
        target["target_review_count"] = target_review_count
    return client.post(
        "/api/integration/v1/crawl-jobs",
        headers={"Idempotency-Key": key},
        json={"slot": "morning", "targets": [target]},
    )


def test_enqueue_is_non_blocking_and_idempotent(session_factory):
    client = make_client(session_factory, principal(1, 1))
    first = enqueue(client)
    second = enqueue(client)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["batch_id"] == second.json()["data"]["batch_id"]
    assert first.json()["data"]["status"] == "queued"
    assert first.json()["data"]["jobs"][0]["onebox_location_id"] == 101
    assert first.json()["data"]["jobs"][0]["target_review_count"] == 2
    assert first.json()["data"]["review_counts"] == {
        "target": 2,
        "scanned": 0,
        "fetched": 0,
        "matched": 0,
        "out_of_range": 0,
        "out_of_range_newer": 0,
        "out_of_range_older": 0,
        "inserted": 0,
        "duplicate": 0,
        "failed": 0,
    }
    with session_factory() as session:
        assert len(list(session.scalars(select(CrawlBatch)))) == 1
        assert len(list(session.scalars(select(CrawlJob)))) == 1


def test_idempotency_key_rejects_different_payload(session_factory):
    client = make_client(session_factory, principal(1, 1))
    assert enqueue(client).status_code == 202
    response = enqueue(client, location_id=102)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_target_review_count_override_is_queued_and_idempotent(session_factory):
    client = make_client(session_factory, principal(1, 1))
    key = "169:2026-07-29:manual-10"

    first = enqueue(client, key=key, target_review_count=10)
    second = enqueue(client, key=key, target_review_count=10)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["batch_id"] == second.json()["data"]["batch_id"]
    assert first.json()["data"]["jobs"][0]["target_review_count"] == 10
    with session_factory() as session:
        job = session.scalar(select(CrawlJob))
        assert job.target_review_count == 10


def test_idempotency_rejects_different_target_review_count(session_factory):
    client = make_client(session_factory, principal(1, 1))
    key = "169:2026-07-29:manual-target-conflict"

    assert enqueue(client, key=key, target_review_count=10).status_code == 202
    response = enqueue(client, key=key, target_review_count=20)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_new_window_payload_normalizes_options(session_factory):
    client = make_client(session_factory, principal(1, 1))
    response = client.post(
        "/api/integration/v1/crawl-jobs",
        headers={"Idempotency-Key": "169:2026-09-01:window-v2"},
        json={
            "slot": "manual",
            "crawl_mode": "custom_range",
            "max_reviews_to_collect": 5,
            "scan_limit": 40,
            "date_range": {
                "from": "2026-08-01T00:00:00+07:00",
                "to": "2026-09-01T00:00:00+07:00",
            },
            "targets": [{"onebox_location_id": 101}],
        },
    )

    assert response.status_code == 202
    data = response.json()["data"]
    job = data["jobs"][0]
    assert job["target_review_count"] == 5
    assert job["max_reviews_to_collect"] == 5
    assert job["scan_limit"] == 40
    assert job["crawl_mode"] == "custom_range"
    assert data["limits"] == {"max_reviews_to_collect": 5, "scan_limit": 40}

    with session_factory() as session:
        stored = session.scalar(select(CrawlJob))
        assert stored.target_review_count == 5
        assert stored.result_json["request"]["crawl_mode"] == "custom_range"
        assert stored.result_json["request"]["scan_limit"] == 40


def test_same_target_window_returns_active_batch(session_factory):
    client = make_client(session_factory, principal(1, 1))

    first = enqueue(client, key="169:2026-09-01:first-active")
    second = enqueue(client, key="169:2026-09-01:second-active")

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["data"]["batch_id"] == first.json()["data"]["batch_id"]
    assert second.json()["data"]["reused_existing_job"] is True
    with session_factory() as session:
        assert len(list(session.scalars(select(CrawlBatch)))) == 1
        assert len(list(session.scalars(select(CrawlJob)))) == 1


def test_tenant_cannot_enqueue_or_read_another_tenants_target(session_factory):
    tenant_a = make_client(session_factory, principal(1, 1))
    batch_id = enqueue(tenant_a).json()["data"]["batch_id"]
    tenant_b = make_client(session_factory, principal(2, 2))

    cross_enqueue = enqueue(tenant_b, location_id=101, key="169:2026-07-29:tenant-b")
    cross_read = tenant_b.get(f"/api/integration/v1/crawl-jobs/{batch_id}")
    assert cross_enqueue.status_code == 404
    assert cross_read.status_code == 404


def test_scope_is_enforced(session_factory):
    client = make_client(session_factory, principal(1, 1, scopes=["reviews:read"]))
    response = enqueue(client)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_worker_claims_and_completes_job(session_factory):
    class FakeFetchService:
        def fetch_location(
            self,
            location_id,
            target,
            date_from=None,
            date_to=None,
            on_progress=None,
            sort_by="newest",
            scan_limit=None,
            time_limit_seconds=0,
        ):
            if on_progress is not None:
                on_progress(1, target)
            return {
                "status": "success",
                "location_id": location_id,
                "target_review_count": target,
                "metadata": {
                    "reviews_scanned": 2,
                    "matched_review_cards": 2,
                    "place_rating": 4.3,
                    "place_review_count": 9422,
                    "rating_snapshot_at": "2026-09-01T06:00:00+00:00",
                    "rating_snapshot": {
                        "source": "google_maps",
                        "place_rating": 4.3,
                        "place_review_count": 9422,
                        "snapshot_at": "2026-09-01T06:00:00+00:00",
                    },
                },
                "total_fetched": 2,
                "total_inserted": 2,
                "total_duplicate": 0,
                "total_skipped_out_of_range": 0,
            }

    settings = replace(
        get_settings(),
        crawl_worker_max_attempts=3,
        crawl_worker_lease_seconds=300,
        crawl_worker_retry_base_seconds=1,
    )
    service = CrawlJobService(
        session_factory=session_factory,
        settings=settings,
        fetch_service_factory=lambda _company_id: FakeFetchService(),
    )
    queued, created = service.enqueue(
        company_id=1,
        client_id=1,
        idempotency_key="169:2026-07-29:worker",
        onebox_location_ids=[101],
        slot="morning",
    )
    assert created is True

    completed = service.execute_next(worker_id="test-worker")
    assert completed["batch_id"] == queued["batch_id"]
    assert completed["status"] == "completed"
    assert completed["jobs"][0]["status"] == "succeeded"
    assert completed["jobs"][0]["onebox_location_id"] == 101
    assert completed["jobs"][0]["result"]["total_inserted"] == 2
    assert completed["jobs"][0]["rating_snapshot"] == {
        "source": "google_maps",
        "place_rating": 4.3,
        "place_review_count": 9422,
        "snapshot_at": "2026-09-01T06:00:00+00:00",
    }
    assert completed["review_counts"] == {
        "target": 2,
        "scanned": 2,
        "fetched": 2,
        "matched": 2,
        "out_of_range": 0,
        "out_of_range_newer": 0,
        "out_of_range_older": 0,
        "inserted": 2,
        "duplicate": 0,
        "failed": 0,
    }


def test_worker_marks_partial_success_without_failed_retry(session_factory):
    class FakeFetchService:
        def fetch_location(
            self,
            location_id,
            target,
            date_from=None,
            date_to=None,
            on_progress=None,
            sort_by="newest",
            scan_limit=None,
            time_limit_seconds=0,
        ):
            return {
                "status": "partial_success",
                "location_id": location_id,
                "target_review_count": target,
                "metadata": {
                    "reviews_scanned": 50,
                    "matched_review_cards": 0,
                    "stopped_reason": "sort_unavailable",
                },
                "total_fetched": 0,
                "total_inserted": 0,
                "total_duplicate": 0,
                "total_skipped_out_of_range": 0,
                "total_failed": 0,
            }

    service = CrawlJobService(
        session_factory=session_factory,
        fetch_service_factory=lambda _company_id: FakeFetchService(),
    )
    queued, _ = service.enqueue(
        company_id=1,
        client_id=1,
        idempotency_key="169:2026-07-29:partial",
        onebox_location_ids=[101],
        slot="morning",
    )

    completed = service.execute_next(worker_id="test-worker")

    assert completed["batch_id"] == queued["batch_id"]
    assert completed["status"] == "completed"
    assert completed["counts"]["partial_success"] == 1
    assert completed["stop_reason"] == "sort_unavailable"
    assert completed["stop_reasons"] == {"sort_unavailable": 1}
    assert completed["jobs"][0]["status"] == "partial_success"
    assert completed["jobs"][0]["result"]["metadata"]["stopped_reason"] == (
        "sort_unavailable"
    )
    latest = service.list_batches(company_id=1, limit=1)[0]
    assert "jobs" not in latest
    assert latest["stop_reason"] == "sort_unavailable"
    assert latest["stop_reasons"] == {"sort_unavailable": 1}
