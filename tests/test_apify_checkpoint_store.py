from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, Location
from app.integrations.apify_review_client import ApifyReviewClient
from app.integrations.apify_token_pool import ApifyTokenPool
from app.services.apify_checkpoint_store import ApifyCheckpoint, ApifyCheckpointStore
from app.services.crawl_target import CrawlTarget


def seeded_store():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        company = Company(name="Test")
        session.add(company)
        session.flush()
        location = Location(
            company_id=company.id,
            hospital_name="Hermina",
            branch_name="Hermina Bogor",
            source="google_places",
            external_place_id="place-bogor",
            target_review_count=1,
        )
        session.add(location)
        session.commit()
        target = CrawlTarget.from_location(location)
    return session_factory, ApifyCheckpointStore(session_factory), target


def checkpoint(sort_by="newest"):
    return ApifyCheckpoint(
        sort_by=sort_by,
        review_time=datetime(2026, 6, 1, tzinfo=timezone.utc),
        review_id="review-1",
        recorded_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )


def test_checkpoint_never_narrows_the_requested_window():
    # The checkpoint is the OLDEST review read (newest-first order). Using it as
    # a lower bound would skip every older review that was never read.
    _, store, target = seeded_store()
    store.save(target, checkpoint())
    requested = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert store.resolve_effective_lower_bound(target, "newest", requested) == (
        "newest",
        requested,
    )
    assert store.resolve_effective_lower_bound(target, "newest", None) == (
        "newest",
        None,
    )
    assert store.load(target) is not None


def test_different_sort_discards_checkpoint_and_uses_requested_date(caplog):
    _, store, target = seeded_store()
    store.save(target, checkpoint())
    requested = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert store.resolve_effective_lower_bound(target, "most_relevant", requested) == (
        "most_relevant",
        requested,
    )
    assert store.load(target) is None
    assert "newest" in caplog.text and "most_relevant" in caplog.text


class CompletedApifyClient:
    def start_run(self, actor_id, input, *, token):
        return "run-1", "dataset-1"

    def get_run_status(self, run_id, *, token):
        return "SUCCEEDED"

    def iter_dataset_items(self, dataset_id, *, token):
        yield {
            "review_id": "review-2",
            "place_id": "place-bogor",
            "rating": 5,
            "content": "Good",
            "reviewed_at_date": "2026-08-01T00:00:00Z",
            "scraped_at": "2026-09-15T00:00:00Z",
        }


def test_natural_completion_clears_stale_checkpoint():
    _, store, target = seeded_store()
    store.save(target, checkpoint())
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:", apify_api_tokens=["token-a"]
    )
    client = ApifyReviewClient(
        settings,
        ApifyTokenPool(settings.apify_api_tokens),
        store,
        apify_client=CompletedApifyClient(),
    )

    assert len(client.fetch_reviews(target, limit=1)) == 1
    assert store.load(target) is None
