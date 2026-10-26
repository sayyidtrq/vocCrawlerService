"""MT-40: tenant fairness and caps on the durable crawl queue."""

from datetime import datetime, timedelta, timezone
from itertools import groupby
from uuid import uuid4

import pytest

from app.config import Settings, _EnvSettings
from app.db.models import ApiClient, Company, CrawlBatch, CrawlJob
from app.services.crawl_worker import CrawlWorker

# SQLite cannot exercise FOR UPDATE SKIP LOCKED or concurrent tenant row locks.


def add_tenant(factory, *, weight=1, active=True):
    with factory() as session:
        company = Company(name="Tenant", weight=weight, is_active=active)
        session.add(company)
        session.flush()
        client = ApiClient(
            company_id=company.id,
            name="onebox",
            key_id=str(uuid4()),
            secret_hash="h",
            scopes=["crawl:enqueue"],
        )
        session.add(client)
        session.flush()
        batch = CrawlBatch(
            public_id=str(uuid4()),
            company_id=company.id,
            requested_by_client_id=client.id,
            idempotency_key=str(uuid4()),
            request_fingerprint="f" * 64,
        )
        session.add(batch)
        session.commit()
        return batch


def add_job(factory, batch, **overrides):
    values = {
        "batch_id": batch.id,
        "company_id": batch.company_id,
        "source_snapshot": "google_maps",
        "target_review_count": 2,
        "available_at": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    values.update(overrides)
    with factory() as session:
        job = CrawlJob(**values)
        session.add(job)
        session.commit()
        return job


@pytest.fixture()
def worker(tx_session_factory, tx_settings):
    return CrawlWorker(
        session_factory=tx_session_factory,
        settings=tx_settings,
        fetch_service_factory=lambda _company_id: None,
    )


def test_weight_three_gets_three_quarters_of_claims_without_draining_a_tenant(
    tx_session_factory,
    worker,
):
    heavy = add_tenant(tx_session_factory, weight=3)
    light = add_tenant(tx_session_factory)
    for batch in (heavy, light):
        for _ in range(40):
            add_job(tx_session_factory, batch)

    claims = [worker.claim_next(worker_id="worker").company_id for _ in range(40)]

    assert 28 <= claims.count(heavy.company_id) <= 32
    assert set(claims[:4]) == {heavy.company_id, light.company_id}
    assert max(len(list(group)) for _, group in groupby(claims)) <= 3


@pytest.mark.parametrize("status", ["queued", "retry_wait", "awaiting_source"])
def test_idle_future_and_inactive_tenants_do_not_block_due_work(
    tx_session_factory,
    worker,
    status,
):
    add_tenant(tx_session_factory, weight=100)
    future = add_tenant(tx_session_factory, weight=100)
    add_job(
        tx_session_factory,
        future,
        status=status,
        available_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    inactive = add_tenant(tx_session_factory, active=False, weight=100)
    skipped = add_job(tx_session_factory, inactive, status=status)
    active = add_tenant(tx_session_factory)
    due = add_job(tx_session_factory, active, status=status)

    assert worker.claim_next(worker_id="worker").id == due.id
    assert worker.claim_next(worker_id="worker") is None
    with tx_session_factory() as session:
        assert session.get(CrawlJob, skipped.id).status == status


def test_cap_redirects_work_and_returns_none_when_only_capped_tenant_remains(
    tx_session_factory,
    worker,
    tx_settings,
):
    worker.settings = tx_settings.model_copy(
        update={"crawl_max_concurrency_per_tenant": 2}
    )
    capped = add_tenant(tx_session_factory)
    now = datetime.now(timezone.utc)
    for _ in range(2):
        add_job(
            tx_session_factory,
            capped,
            status="running",
            lease_expires_at=now + timedelta(hours=1),
            started_at=now - timedelta(hours=2),
        )
    waiting = add_job(tx_session_factory, capped)
    other = add_tenant(tx_session_factory)
    available = add_job(tx_session_factory, other)

    assert worker.claim_next(worker_id="worker").id == available.id
    assert worker.claim_next(worker_id="worker") is None
    with tx_session_factory() as session:
        assert session.get(CrawlJob, waiting.id).status == "queued"


def test_zero_cap_allows_more_claims_with_existing_running_jobs(
    tx_session_factory, worker
):
    batch = add_tenant(tx_session_factory)
    for _ in range(2):
        add_job(
            tx_session_factory,
            batch,
            status="running",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    due = [add_job(tx_session_factory, batch) for _ in range(3)]

    assert worker.settings.crawl_max_concurrency_per_tenant == 0
    assert [worker.claim_next(worker_id="worker").id for _ in due] == [
        job.id for job in due
    ]
    assert worker.claim_next(worker_id="worker") is None


@pytest.mark.parametrize("mode", [None, "regular_delta", "custom_range", "unknown"])
def test_non_backfill_jobs_precede_older_initial_backfill(
    tx_session_factory, worker, mode
):
    batch = add_tenant(tx_session_factory)
    backfill = add_job(
        tx_session_factory,
        batch,
        result_json={"request": {"crawl_mode": "initial_backfill"}},
    )
    delta = add_job(
        tx_session_factory,
        batch,
        result_json={"request": {"crawl_mode": mode}} if mode else {},
    )

    assert worker.claim_next(worker_id="worker").id == delta.id
    assert worker.claim_next(worker_id="worker").id == backfill.id


def test_single_tenant_orders_by_available_at_then_id(tx_session_factory, worker):
    batch = add_tenant(tx_session_factory)
    now = datetime.now(timezone.utc)
    later = add_job(tx_session_factory, batch, available_at=now - timedelta(minutes=1))
    oldest = add_job(tx_session_factory, batch, available_at=now - timedelta(minutes=2))
    tied = add_job(tx_session_factory, batch, available_at=oldest.available_at)

    assert [worker.claim_next(worker_id="worker").id for _ in range(3)] == [
        oldest.id,
        tied.id,
        later.id,
    ]


def test_tenant_score_ties_use_the_oldest_due_jobs_actual_id(
    tx_session_factory, worker
):
    first = add_tenant(tx_session_factory)
    second = add_tenant(tx_session_factory)
    now = datetime.now(timezone.utc)
    add_job(tx_session_factory, first, available_at=now - timedelta(minutes=1))
    expected = add_job(
        tx_session_factory, second, available_at=now - timedelta(minutes=2)
    )
    add_job(tx_session_factory, first, available_at=expected.available_at)

    assert worker.claim_next(worker_id="worker").id == expected.id


@pytest.mark.parametrize("age_seconds, expected_first", [(60, False), (180, True)])
def test_score_counts_completed_jobs_only_inside_the_configured_window(
    tx_session_factory,
    worker,
    tx_settings,
    age_seconds,
    expected_first,
):
    worker.settings = tx_settings.model_copy(
        update={"crawl_fairness_window_seconds": 120}
    )
    first = add_tenant(tx_session_factory)
    second = add_tenant(tx_session_factory)
    add_job(
        tx_session_factory,
        first,
        status="succeeded",
        started_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    )
    due_first = add_job(tx_session_factory, first)
    due_second = add_job(tx_session_factory, second)

    expected = due_first if expected_first else due_second
    assert worker.claim_next(worker_id="worker").id == expected.id


def test_expired_running_job_is_recovered_without_using_a_cap_slot(
    tx_session_factory,
    worker,
    tx_settings,
):
    worker.settings = tx_settings.model_copy(
        update={"crawl_max_concurrency_per_tenant": 1}
    )
    batch = add_tenant(tx_session_factory)
    now = datetime.now(timezone.utc)
    # Missing leases and completed jobs do not consume live concurrency slots.
    add_job(tx_session_factory, batch, status="running", lease_expires_at=None)
    add_job(
        tx_session_factory,
        batch,
        status="succeeded",
        lease_expires_at=now + timedelta(hours=1),
    )
    expired = add_job(
        tx_session_factory,
        batch,
        status="running",
        attempts=1,
        lease_expires_at=now - timedelta(seconds=1),
        started_at=now - timedelta(hours=2),
        result_json={"source_run": {"run_id": "existing-run"}},
    )

    claimed = worker.claim_next(worker_id="recovery-worker")

    assert claimed.id == expired.id and claimed.attempts == 2
    assert claimed.source_run == {"run_id": "existing-run"}
    with tx_session_factory() as session:
        stored = session.get(CrawlJob, expired.id)
        assert stored.locked_by == "recovery-worker"
        assert stored.started_at == expired.started_at.replace(tzinfo=None)
        assert stored.lease_expires_at > now.replace(tzinfo=None)


def test_fairness_settings_load_environment_and_blank_defaults(monkeypatch):
    monkeypatch.setenv("CRAWL_FAIRNESS_WINDOW_SECONDS", "120")
    monkeypatch.setenv("CRAWL_MAX_CONCURRENCY_PER_TENANT", "2")
    configured = _EnvSettings(database_url="sqlite://", onebox_tenant_mode="single")
    assert configured.crawl_fairness_window_seconds == 120
    assert configured.crawl_max_concurrency_per_tenant == 2

    monkeypatch.setenv("CRAWL_FAIRNESS_WINDOW_SECONDS", " ")
    monkeypatch.setenv("CRAWL_MAX_CONCURRENCY_PER_TENANT", "")
    defaults = _EnvSettings(database_url="sqlite://", onebox_tenant_mode="single")
    assert defaults.crawl_fairness_window_seconds == 3600
    assert defaults.crawl_max_concurrency_per_tenant == 0
    assert Settings(database_url="sqlite://").crawl_max_concurrency_per_tenant == 0
