"""Parked Apify runs: the worker never waits on a run (spec CS-3)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import ApiClient, Company, CrawlJob, Location, Review
from app.integrations.apify_review_client import ApifyReviewClient
from app.integrations.apify_token_pool import ApifyTokenPool
from app.services.apify_checkpoint_store import ApifyCheckpointStore
from app.services.apify_fetch_service import ApifyFetchService
from app.services.crawl_queue import CrawlQueue
from app.services.crawl_worker import CrawlWorker

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "apify_google_maps_reviews_sample.json").read_text()
)


class FakeApify:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.started = 0
        self.aborted = 0
        self.polls = 0

    def start_run(self, actor_id, input, *, token):
        self.started += 1
        return f"run-{self.started}", f"dataset-{self.started}"

    def get_run_status_once(self, run_id, *, token):
        self.polls += 1
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def dataset_item_count(self, dataset_id, *, token):
        return 1

    def iter_dataset_items(self, dataset_id, *, token):
        yield from FIXTURE[:2]

    def abort_run(self, run_id, *, token):
        self.aborted += 1

    def get_run_status(self, run_id, *, token):  # pragma: no cover - sync path
        raise AssertionError("the worker must never block on a run")


def setup(statuses, **settings_overrides):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        company = Company(name="Test", total_enable_review=0)
        session.add(company)
        session.flush()
        api_client = ApiClient(
            company_id=company.id,
            name="onebox",
            key_id="k",
            secret_hash="h",
            scopes=["crawl:enqueue"],
        )
        location = Location(
            company_id=company.id,
            hospital_name="Hermina",
            branch_name="Hermina Bekasi",
            source="apify_google_maps",
            external_place_id="place-1",
            onebox_location_id=101,
            crawl_enabled=True,
            ingest_reviews=True,
            is_active=True,
        )
        session.add_all([api_client, location])
        session.commit()
        company_id, client_id = company.id, api_client.id
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        apify_api_tokens=["token-a"],
        crawl_source_poll_seconds=0,
        **settings_overrides,
    )
    fake = FakeApify(statuses)
    pool = ApifyTokenPool(settings.apify_api_tokens)

    def factory_for(company):
        return ApifyFetchService(
            company_id=company,
            session_factory=factory,
            settings=settings,
            client=ApifyReviewClient(
                settings, pool, ApifyCheckpointStore(factory), apify_client=fake
            ),
        )

    worker = CrawlWorker(
        session_factory=factory, settings=settings, fetch_service_factory=factory_for
    )
    CrawlQueue(session_factory=factory, settings=settings).enqueue(
        company_id=company_id,
        client_id=client_id,
        idempotency_key="parked-run-test",
        slot="manual",
        onebox_location_ids=[101],
        target_crawl_options={
            101: {"coverage": "delta", "budget": None, "crawl_mode": None}
        },
    )
    return factory, worker, fake


def job(factory):
    with factory() as session:
        return session.scalar(select(CrawlJob))


def test_running_run_is_parked_then_finished_with_one_actor_run():
    factory, worker, fake = setup(["RUNNING", "RUNNING", "RUNNING", "SUCCEEDED"])

    worker.execute_next(worker_id="w")  # start
    parked = job(factory)
    assert parked.status == "awaiting_source"
    assert parked.lease_expires_at is None
    assert parked.result_json["source_run"]["run_id"] == "run-1"

    for _ in range(3):  # RUNNING x3
        batch = worker.execute_next(worker_id="w")
        assert batch["jobs"][0]["status"] == "running"  # public view
        assert job(factory).status == "awaiting_source"
    worker.execute_next(worker_id="w")  # SUCCEEDED

    done = job(factory)
    assert fake.started == 1
    assert done.status == "succeeded"
    assert done.attempts == 1, "polls must not count as attempts"
    assert "source_run" not in done.result_json
    with factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 2


def test_run_past_the_deadline_is_aborted_and_not_retried():
    factory, worker, fake = setup(["RUNNING"], apify_backfill_deadline_seconds=60)
    worker.execute_next(worker_id="w")
    with factory() as session:
        row = session.scalar(select(CrawlJob))
        result = dict(row.result_json)
        run = dict(result["source_run"])
        run["started_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=120)
        ).isoformat()
        result["source_run"] = run
        row.result_json = result
        session.commit()

    worker.execute_next(worker_id="w")

    done = job(factory)
    assert fake.aborted == 1
    assert fake.started == 1
    assert done.status == "failed"
    assert done.last_error_code == "APIFY_RUN_DEADLINE_EXCEEDED"
    assert done.result_json["metadata"]["stop_reason"] == "deadline_exceeded"
    with factory() as session:
        # Whatever the dataset already had is kept.
        assert session.scalar(select(func.count(Review.id))) == 2


def test_expired_lease_mid_poll_resumes_the_same_run():
    factory, worker, fake = setup(["RUNNING", "SUCCEEDED"])
    worker.execute_next(worker_id="w")
    with factory() as session:
        row = session.scalar(select(CrawlJob))
        # Worker died while checking: status running, lease already expired.
        row.status = "running"
        row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()

    worker.execute_next(worker_id="w")  # reclaimed -> RUNNING -> parked again
    worker.execute_next(worker_id="w")  # SUCCEEDED

    assert fake.started == 1
    assert job(factory).status == "succeeded"


def test_sync_path_is_kept_when_parking_is_disabled():
    factory, worker, fake = setup(["SUCCEEDED"], crawl_async_source_runs=False)
    fake.get_run_status = lambda run_id, *, token: "SUCCEEDED"

    worker.execute_next(worker_id="w")

    assert job(factory).status == "succeeded"
    assert fake.polls == 0
