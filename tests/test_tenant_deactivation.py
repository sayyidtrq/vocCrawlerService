"""MT-23: inactive tenants retain data while waiting crawls are cancelled."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.tenant_registry_service as registry_module
import apps.api.app_api.service_auth as service_auth_module
from app.config import get_settings
from app.db.base import Base
from app.db.models import Company, CrawlBatch, CrawlJob, Location, Review
from app.services.api_client_service import ApiClientService
from app.services.crawl_queue import CrawlQueue, CrawlQueueError
from app.services.crawl_worker import CrawlWorker
from app.services.tenant_registry_service import TenantRegistryService
from apps.api.app_api.routers.integration_crawl_jobs import get_crawl_queue_session_factory
from apps.api.main import create_app

WAITING = ("queued", "retry_wait", "awaiting_source")
TERMINAL = ("succeeded", "partial_success", "skipped", "failed", "cancelled")


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def settings():
    return get_settings().model_copy(update={
        "app_env": "local",
        "service_token_pepper": "test-pepper",
        "onebox_tenant_mode": "managed",
        "auto_analyze_on_crawl": False,
    })


@pytest.fixture()
def registry(session_factory, settings):
    return TenantRegistryService(session_factory=session_factory, settings=settings)


@pytest.fixture()
def tenant(registry):
    return registry.register(177, "Tenant A")


@pytest.fixture()
def location(session_factory, tenant):
    with session_factory() as session:
        location = Location(
            company_id=tenant.view.company_id,
            organization_name="Tenant A",
            branch_name="Branch A",
            source="apify_google_maps",
            external_place_id="place-a",
            onebox_location_id=101,
            target_review_count=2,
        )
        session.add(location)
        session.commit()
        return location


@pytest.fixture()
def queue(session_factory, settings):
    return CrawlQueue(session_factory=session_factory, settings=settings)


@pytest.fixture()
def worker(session_factory, settings):
    return CrawlWorker(
        session_factory=session_factory,
        settings=settings,
        fetch_service_factory=lambda _company_id: None,
    )


def add_batch(session_factory, tenant, statuses, *, batch_status="queued"):
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        batch = CrawlBatch(
            public_id=str(uuid4()),
            company_id=tenant.view.company_id,
            requested_by_client_id=tenant.token.client.id,
            idempotency_key=str(uuid4()),
            request_fingerprint="f" * 64,
            status=batch_status,
            finished_at=now if batch_status in ("failed", "partial_failed") else None,
        )
        session.add(batch)
        session.flush()
        jobs = []
        for status in statuses:
            location = Location(
                company_id=tenant.view.company_id,
                organization_name=tenant.view.site_name,
                branch_name=status,
                source="apify_google_maps",
                external_place_id=str(uuid4()),
            )
            session.add(location)
            session.flush()
            job = CrawlJob(
                batch_id=batch.id,
                company_id=tenant.view.company_id,
                location_id=location.id,
                status=status,
                source_snapshot=location.source,
                target_review_count=2,
                available_at=now - timedelta(minutes=5),
                locked_by="old-worker",
                locked_at=now - timedelta(minutes=1),
                lease_expires_at=now + timedelta(minutes=5),
                started_at=now - timedelta(minutes=1),
                finished_at=now if status in TERMINAL else None,
                last_error_code="PREVIOUS_ERROR",
                last_error="Previous error.",
                result_json={"request": {"coverage": "delta"}, "total_inserted": 1},
            )
            session.add(job)
            jobs.append(job)
        session.commit()
        return batch, jobs


def rows(session_factory, model):
    with session_factory() as session:
        return {
            row["id"]: dict(row)
            for row in session.execute(
                select(model.__table__).order_by(model.id)
            ).mappings()
        }


def enqueue(queue, tenant, key="tenant-crawl-original", location_id=101):
    return queue.enqueue(
        company_id=tenant.view.company_id,
        client_id=tenant.token.client.id,
        idempotency_key=key,
        onebox_location_ids=[location_id],
        slot=None,
    )


def test_deactivation_cancels_only_tenants_waiting_jobs(
    session_factory, registry, tenant,
):
    batch, jobs = add_batch(session_factory, tenant, (*WAITING, "running", *TERMINAL))
    other = registry.register(200, "Tenant B")
    other_batch, other_jobs = add_batch(session_factory, other, WAITING)
    before = rows(session_factory, CrawlJob)
    other_batch_before = rows(session_factory, CrawlBatch)[other_batch.id]
    statements = []

    def record_update(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lower().startswith("update crawl_jobs "):
            statements.append(statement)

    engine = session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", record_update)
    try:
        registry.update(177, active=False)
    finally:
        event.remove(engine, "before_cursor_execute", record_update)

    assert len(statements) == 1
    after = rows(session_factory, CrawlJob)
    deactivated_at = rows(session_factory, Company)[tenant.view.company_id]["deactivated_at"]
    for job in jobs[:3]:
        cancelled = after[job.id]
        assert cancelled["status"] == "cancelled"
        assert cancelled["finished_at"] == deactivated_at
        assert cancelled["last_error_code"] == "TENANT_INACTIVE"
        assert cancelled["last_error"] == "Tenant was deactivated."
        assert cancelled["locked_by"] is None
        assert cancelled["locked_at"] is None
        assert cancelled["lease_expires_at"] is None
        for field in ("result_json", "attempts", "started_at", "available_at"):
            assert cancelled[field] == before[job.id][field]
    for job in [*jobs[3:], *other_jobs]:
        assert after[job.id] == before[job.id]
    batches = rows(session_factory, CrawlBatch)
    assert batches[batch.id]["status"] == "running"
    assert batches[batch.id]["finished_at"] is None
    assert batches[other_batch.id] == other_batch_before


@pytest.mark.parametrize("statuses, expected", [
    (WAITING, "cancelled"),
    (("succeeded", "partial_success", "skipped", "queued"), "cancelled"),
    (("failed", "queued"), "partial_failed"),
    (("failed", "succeeded", "awaiting_source"), "partial_failed"),
])
def test_deactivation_recomputes_each_affected_batch(
    session_factory, registry, tenant, statuses, expected,
):
    first, _ = add_batch(session_factory, tenant, statuses)
    second, _ = add_batch(session_factory, tenant, ["queued"])
    failed, _ = add_batch(session_factory, tenant, ["failed"], batch_status="failed")
    failed_before = rows(session_factory, CrawlBatch)[failed.id]

    registry.update(177, active=False)

    batches = rows(session_factory, CrawlBatch)
    assert batches[first.id]["status"] == expected
    assert batches[first.id]["finished_at"] is not None
    assert batches[second.id]["status"] == "cancelled"
    assert batches[second.id]["finished_at"] == batches[first.id]["finished_at"]
    assert batches[failed.id] == failed_before


@pytest.mark.parametrize("status, expected", [
    ("succeeded", "cancelled"),
    ("failed", "partial_failed"),
])
def test_running_job_can_finish_after_deactivation(
    session_factory, registry, tenant, worker, status, expected,
):
    batch, jobs = add_batch(session_factory, tenant, ["queued", "queued"])
    claimed = worker.claim_next(worker_id="test-worker")
    assert claimed.id == jobs[0].id

    registry.update(177, active=False)
    result = worker._finish(claimed, status=status, result={"total_inserted": 1})

    assert result["batch_id"] == batch.public_id
    assert result["status"] == expected
    assert result["jobs"][0]["status"] == status
    assert result["jobs"][1]["status"] == "cancelled"
    assert result["counts"]["cancelled"] == 1
    assert result["finished_at"] is not None


def test_deactivation_preserves_reviews_and_locations(
    session_factory, registry, tenant, location, queue,
):
    enqueue(queue, tenant)
    with session_factory() as session:
        session.add(Review(
            company_id=tenant.view.company_id,
            location_id=location.id,
            source=location.source,
            review_hash="retained-review",
            review_text="Keep this review.",
            rating=4,
        ))
        session.commit()
    before = {model: rows(session_factory, model) for model in (Location, Review)}

    registry.update(177, active=False)

    for model, snapshot in before.items():
        assert rows(session_factory, model) == snapshot


def test_second_deactivation_is_noop_even_with_new_waiting_jobs(
    session_factory, registry, tenant,
):
    add_batch(session_factory, tenant, WAITING)
    registry.update(177, active=False)
    add_batch(session_factory, tenant, ["queued"])
    before = {model: rows(session_factory, model) for model in (Company, CrawlBatch, CrawlJob)}

    registry.update(177, active=False)

    for model, snapshot in before.items():
        assert rows(session_factory, model) == snapshot


def test_reactivation_leaves_cancelled_jobs_and_allows_new_enqueue(
    session_factory, registry, tenant, location, queue,
):
    original, _ = enqueue(queue, tenant)
    registry.update(177, active=False)
    cancelled = rows(session_factory, CrawlJob)

    view = registry.update(177, active=True)

    assert view.is_active is True and view.deactivated_at is None
    assert rows(session_factory, CrawlJob) == cancelled
    new, created = enqueue(queue, tenant, key="tenant-crawl-after-reactivation")
    assert created is True and new["batch_id"] != original["batch_id"]
    assert new["jobs"][0]["status"] == "queued"


@pytest.mark.parametrize("location_id", [101, 999])
def test_inactive_tenant_cannot_enqueue_or_refresh_worklist(
    session_factory, registry, tenant, location, queue, monkeypatch, location_id,
):
    registry.update(177, active=False)
    before = {model: rows(session_factory, model) for model in (CrawlBatch, CrawlJob, Location)}

    def unexpected_refresh(*_args):
        pytest.fail("An inactive tenant must be rejected before worklist refresh.")

    monkeypatch.setattr(queue, "_refresh_worklist_once", unexpected_refresh)
    with pytest.raises(CrawlQueueError) as error:
        enqueue(queue, tenant, location_id=location_id)

    assert (error.value.status_code, error.value.code) == (409, "TENANT_INACTIVE")
    for model, snapshot in before.items():
        assert rows(session_factory, model) == snapshot


def test_inactive_tenant_can_replay_existing_idempotency_key(
    session_factory, registry, tenant, location, queue,
):
    original, _ = enqueue(queue, tenant)
    registry.update(177, active=False)
    before = rows(session_factory, CrawlBatch), rows(session_factory, CrawlJob)

    replay, created = enqueue(queue, tenant)

    assert created is False
    assert replay == queue.get_batch(company_id=tenant.view.company_id, public_id=original["batch_id"])
    assert replay["status"] == "cancelled"
    assert replay["counts"]["cancelled"] == 1
    with pytest.raises(CrawlQueueError) as error:
        enqueue(queue, tenant, location_id=999)
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    assert (rows(session_factory, CrawlBatch), rows(session_factory, CrawlJob)) == before


def test_inactive_tenant_http_enqueue_replay_and_read_tokens(
    session_factory, settings, registry, tenant, location, monkeypatch,
):
    tokens = ApiClientService(session_factory=session_factory, settings=settings)
    monkeypatch.setattr(service_auth_module, "ApiClientService", lambda: tokens)
    application = create_app()
    application.dependency_overrides[get_crawl_queue_session_factory] = lambda: session_factory
    client = TestClient(application)
    headers = {
        "Authorization": f"Bearer {tenant.token.token}",
        "Idempotency-Key": "tenant-crawl-http-original",
    }
    payload = {"targets": [{"onebox_location_id": 101}]}
    original = client.post("/api/integration/v1/crawl-jobs", headers=headers, json=payload)
    assert original.status_code == 202
    batch_id = original.json()["data"]["batch_id"]

    registry.update(177, active=False)

    rejected = client.post(
        "/api/integration/v1/crawl-jobs",
        headers={**headers, "Idempotency-Key": "tenant-crawl-http-new"},
        json=payload,
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "TENANT_INACTIVE"
    replay = client.post("/api/integration/v1/crawl-jobs", headers=headers, json=payload)
    assert replay.status_code == 202
    assert replay.json()["data"]["batch_id"] == batch_id
    assert replay.json()["data"]["status"] == "cancelled"
    assert replay.json()["data"]["jobs"][0]["status"] == "cancelled"
    assert replay.json()["data"]["jobs"][0]["error"] == {
        "code": "TENANT_INACTIVE", "message": "Tenant was deactivated.",
    }
    for path in ("/api/integration/v1/crawl-jobs", f"/api/integration/v1/crawl-jobs/{batch_id}"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        batch = data[0] if isinstance(data, list) else data
        assert batch["status"] == "cancelled" and batch["counts"]["cancelled"] == 1
    schemas = client.get("/api/openapi.json").json()["components"]["schemas"]
    for name in ("CrawlJobResponse", "CrawlBatchDataResponse"):
        assert "cancelled" in schemas[name]["properties"]["status"]["enum"]


@pytest.mark.parametrize("status", WAITING)
def test_claim_skips_inactive_waiting_jobs_and_claims_active_tenant(
    session_factory, registry, tenant, worker, status,
):
    registry.update(177, active=False)
    _, inactive_jobs = add_batch(session_factory, tenant, [status])
    other = registry.register(200, "Tenant B")
    _, active_jobs = add_batch(session_factory, other, [status])
    before = rows(session_factory, CrawlJob)[inactive_jobs[0].id]

    claimed = worker.claim_next(worker_id="test-worker")

    assert claimed.id == active_jobs[0].id
    assert claimed.company_id == other.view.company_id
    assert worker.claim_next(worker_id="test-worker") is None
    assert rows(session_factory, CrawlJob)[inactive_jobs[0].id] == before


def test_claim_recovers_expired_running_job_of_inactive_tenant(
    session_factory, registry, tenant, worker,
):
    batch, jobs = add_batch(session_factory, tenant, ["running"])
    with session_factory() as session:
        job = session.get(CrawlJob, jobs[0].id)
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        job.attempts = 1
        job.result_json = {"source_run": {"run_id": "existing-source-run"}}
        session.commit()
    registry.update(177, active=False)

    claimed = worker.claim_next(worker_id="recovery-worker")

    assert claimed.id == jobs[0].id and claimed.batch_id == batch.id
    assert claimed.attempts == 2
    assert claimed.source_run == {"run_id": "existing-source-run"}
    stored = rows(session_factory, CrawlJob)[claimed.id]
    assert stored["status"] == "running" and stored["locked_by"] == "recovery-worker"
    assert stored["lease_expires_at"] > datetime.now(timezone.utc).replace(tzinfo=None)


def test_deactivation_rolls_back_company_and_jobs_if_batch_refresh_fails(
    session_factory, registry, tenant, monkeypatch,
):
    add_batch(session_factory, tenant, WAITING)
    before = {model: rows(session_factory, model) for model in (Company, CrawlBatch, CrawlJob)}

    def fail_refresh(*_args):
        raise RuntimeError("Batch refresh failed.")

    monkeypatch.setattr(registry_module, "refresh_batch_status", fail_refresh)
    with pytest.raises(RuntimeError, match="Batch refresh failed"):
        registry.update(177, active=False)

    for model, snapshot in before.items():
        assert rows(session_factory, model) == snapshot
