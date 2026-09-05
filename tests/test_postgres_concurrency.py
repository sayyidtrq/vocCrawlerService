from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    ApiClient,
    Company,
    CrawlBatch,
    CrawlJob,
    Location,
    Review,
    ReviewAnalysis,
)
from app.services.analysis_service import AnalysisService
from app.services.crawl_job_service import CrawlJobService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="requires TEST_DATABASE_URL (a real Postgres) - see .github/workflows/deploy.yml for the CI service, or run one locally to exercise this file",
)


@pytest.fixture(scope="module")
def pg_session_factory():
    engine = create_engine(
        os.environ["TEST_DATABASE_URL"],
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_claim_next_never_double_claims_under_concurrent_workers(
    pg_session_factory,
):
    with pg_session_factory() as session:
        company = Company(name="Crawl Queue Concurrency")
        session.add(company)
        session.flush()

        api_client = ApiClient(
            company_id=company.id,
            name="concurrency-test",
            key_id="concurrency-test-key",
            secret_hash="0" * 64,
            scopes=["crawl:enqueue"],
        )
        session.add(api_client)
        session.flush()

        batch = CrawlBatch(
            public_id=str(uuid.uuid4()),
            company_id=company.id,
            requested_by_client_id=api_client.id,
            idempotency_key="concurrency-test-key-000",
            request_fingerprint="f" * 40,
            status="queued",
        )
        session.add(batch)
        session.flush()

        for index in range(20):
            location = Location(
                company_id=company.id,
                hospital_name="Concurrency Hospital",
                branch_name=f"Branch {index}",
                source="google_maps",
                external_place_id=f"concurrency-place-{index}",
            )
            session.add(location)
            session.flush()
            session.add(
                CrawlJob(
                    batch_id=batch.id,
                    company_id=company.id,
                    location_id=location.id,
                    onebox_location_id=index,
                    status="queued",
                    source_snapshot="google_maps",
                    target_review_count=10,
                    max_attempts=3,
                )
            )
        session.commit()

    service = CrawlJobService(session_factory=pg_session_factory)

    def claim_until_empty(worker_number):
        claimed = []
        while job := service.claim_next(worker_id=f"worker-{worker_number}"):
            claimed.append(job.id)
        return claimed

    with ThreadPoolExecutor(max_workers=8) as executor:
        claimed_ids = [
            job_id
            for worker_claims in executor.map(claim_until_empty, range(8))
            for job_id in worker_claims
        ]

    assert len(claimed_ids) == 20
    assert len(set(claimed_ids)) == 20


def test_concurrent_analysis_writes_do_not_corrupt_or_deadlock(pg_session_factory):
    with pg_session_factory() as session:
        company = Company(name="Analysis Concurrency")
        session.add(company)
        session.flush()
        location = Location(
            company_id=company.id,
            hospital_name="Analysis Hospital",
            branch_name="Branch A",
            source="google_maps",
            external_place_id="analysis-place-1",
        )
        session.add(location)
        session.flush()
        review = Review(
            company_id=company.id,
            location_id=location.id,
            source="google_maps",
            review_text="Pelayanan sangat baik",
            review_hash="concurrency-review-hash-1",
        )
        session.add(review)
        session.commit()
        review_id = review.id

    service = AnalysisService(company_id=None, session_factory=pg_session_factory)
    cleaned = {
        "sentiment": "positive",
        "sentiment_score": 0.9,
        "issue_category": "general_praise",
        "urgency": "low",
        "summary": "Pelayanan sangat baik",
        "recommended_action": "Tidak ada tindakan",
        "keywords": [],
        "is_potential_viral": False,
        "is_patient_safety_issue": False,
    }

    def store_analysis(attempt):
        service._store_analysis(
            review_id,
            cleaned,
            {"attempt": attempt},
            model_name=f"test-model-{attempt}",
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(store_analysis, range(5)))

    with pg_session_factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(ReviewAnalysis)
            .where(ReviewAnalysis.review_id == review_id)
        )
    assert count == 5
