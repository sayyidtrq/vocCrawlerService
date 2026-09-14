import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import (
    Company,
    Competitor,
    CompetitorReview,
    FetchLog,
    Location,
    Review,
)
from app.integrations.apify_client import ApifyAccountExhaustedError
from app.integrations.apify_review_client import ApifyReviewClient
from app.integrations.apify_token_pool import ApifyTokenPool
from app.services.apify_checkpoint_store import ApifyCheckpointStore
from app.services.apify_fetch_service import ApifyFetchService
from app.services.crawl_target import CrawlTarget


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed_targets(session_factory):
    with session_factory() as session:
        company = Company(name="Test", total_enable_review=100)
        session.add(company)
        session.flush()
        location = Location(
            company_id=company.id,
            hospital_name="Hermina",
            branch_name="Hermina Bekasi",
            source="google_places",
            external_place_id="place-1",
            target_review_count=2,
        )
        competitor = Competitor(
            company_id=company.id,
            name="RS Pesaing",
            source="google_places",
            external_place_id="place-2",
            target_review_count=2,
        )
        session.add_all([location, competitor])
        session.commit()
        return company.id, location, competitor


class FakeApifyReviewClient:
    source_name = "apify_google_maps"

    def __init__(self):
        self.last_metadata = {}

    def fetch_reviews(
        self, crawl_target, limit, sort_by="newest", date_from=None, date_to=None
    ):
        scraped_at = datetime(2026, 9, 1, 6, tzinfo=timezone.utc).isoformat()
        self.last_metadata = {
            "target_review_count": limit,
            "max_reviews_to_collect": limit,
            "reviews_scanned": 2,
            "matched_review_cards": 2,
            "failed_review_cards": 0,
            "sort_by": sort_by,
            "sort_applied": True,
            "place_rating": 4.3,
            "place_review_count": 9422,
            "rating_snapshot_at": scraped_at,
            "rating_snapshot": {
                "source": "google_maps",
                "place_rating": 4.3,
                "place_review_count": 9422,
                "snapshot_at": scraped_at,
            },
        }
        return [
            {
                "source": self.source_name,
                "external_place_id": crawl_target.external_place_id,
                "external_review_id": f"review-{index}",
                "reviewer_name": name,
                "reviewer_profile_url": None,
                "reviewer_photo_url": None,
                "reviewer_local_guide_level": "Local Guide" if index == 1 else None,
                "reviewer_total_reviews": 37 if index == 1 else None,
                "rating": rating,
                "review_text": text,
                "review_time": f"2026-08-0{index}T00:00:00Z",
                "review_relative_time": None,
                "review_language": "id",
                "language": "id",
                "like_count": index,
                "owner_response_text": None,
                "owner_response_time": None,
                "scraped_at": scraped_at,
                "raw_payload": {"index": index},
            }
            for index, (name, rating, text) in enumerate(
                [("Andi", 5, "Baik."), ("Budi", 2, "Lama.")], start=1
            )
        ][:limit]


def make_service(session_factory, company_id):
    return ApifyFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=Settings(
            database_url="sqlite+pysqlite:///:memory:",
            review_source_mode="apify",
            crawl_max_target_reviews=300,
        ),
        client=FakeApifyReviewClient(),
    )


def test_apify_fetch_stores_metadata_deduplicates_and_keeps_result_shape():
    session_factory = make_session_factory()
    company_id, location, _ = seed_targets(session_factory)
    service = make_service(session_factory, company_id)
    progress = []

    first = service.fetch_location(
        location.id,
        target=2,
        on_progress=lambda fetched, total, scanned: progress.append(
            (fetched, total, scanned)
        ),
    )
    second = service.fetch_location(location.id, target=2)

    assert first["status"] == "success"
    assert first["total_inserted"] == 2
    assert second["total_duplicate"] == 2
    assert progress == [(0, 2, 0), (2, 2, 2)]
    assert {
        "status",
        "metadata",
        "error_message",
        "total_fetched",
        "total_inserted",
        "total_duplicate",
        "total_failed",
        "total_skipped_out_of_range",
    } <= first.keys()
    with session_factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 2
        latest_log = session.scalar(
            select(FetchLog).order_by(FetchLog.id.desc()).limit(1)
        )
        assert latest_log.source == "apify_google_maps"
        assert latest_log.metadata_json["rating_snapshot"]["place_review_count"] == 9422


def test_apify_competitor_fetch_stores_reviews_without_fetch_log():
    session_factory = make_session_factory()
    company_id, _, competitor = seed_targets(session_factory)
    service = make_service(session_factory, company_id)

    first = service.fetch_competitor(competitor.id, target=2)
    second = service.fetch_competitor(competitor.id, target=2)

    assert first["status"] == "success"
    assert first["total_inserted"] == 2
    assert second["total_duplicate"] == 2
    with session_factory() as session:
        assert session.scalar(select(func.count(CompetitorReview.id))) == 2
        assert session.scalar(select(func.count(FetchLog.id))) == 0


def test_apify_competitor_result_uses_competitor_keys():
    session_factory = make_session_factory()
    company_id, _, competitor = seed_targets(session_factory)

    result = make_service(session_factory, company_id).fetch_competitor(
        competitor.id, target=2
    )

    assert result["competitor_id"] == competitor.id
    assert result["competitor_name"] == competitor.name
    assert "location_id" not in result
    assert "location_name" not in result


class ExhaustingApifyClient:
    def __init__(self, items):
        self.items = items
        self.actor_inputs = []

    def start_run(self, actor_id, input, *, token):
        self.actor_inputs.append(dict(input))
        return f"run-{token}", f"dataset-{token}"

    def get_run_status(self, run_id, *, token):
        return "SUCCEEDED"

    def iter_dataset_items(self, dataset_id, *, token):
        yield self.items[0 if token == "token-a" else 1]
        raise ApifyAccountExhaustedError("credits exhausted")


def test_both_accounts_exhausted_keeps_partial_reviews_and_checkpoint():
    session_factory = make_session_factory()
    company_id, location, _ = seed_targets(session_factory)
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures" / "apify_google_maps_reviews_sample.json"
        ).read_text()
    )
    low_level = ExhaustingApifyClient([fixture[3], fixture[2]])
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        review_source_mode="apify",
        crawl_max_target_reviews=300,
        apify_api_tokens=["token-a", "token-b"],
    )
    store = ApifyCheckpointStore(session_factory)
    client = ApifyReviewClient(
        settings,
        ApifyTokenPool(settings.apify_api_tokens),
        store,
        apify_client=low_level,
    )
    service = ApifyFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=client,
    )

    result = service.fetch_location(location.id, target=3, sort_by="newest")

    assert result["status"] == "partial_success"
    assert result["total_inserted"] == 2
    assert result["metadata"]["stop_reason"] == "apify_accounts_exhausted"
    checkpoint = store.load(
        CrawlTarget.from_location(service.location_service.get_location(location.id))
    )
    assert checkpoint is not None
    assert checkpoint.sort_by == "newest"
    assert checkpoint.review_id == fixture[2]["review_id"]
    assert checkpoint.review_time == datetime(2026, 5, 17, tzinfo=timezone.utc)
    assert low_level.actor_inputs[1]["newerThan"] == "2026-07-16T00:00:00+00:00"
    assert all(
        actor_input["reviewsOrigin"] == "google"
        for actor_input in low_level.actor_inputs
    )
    with session_factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 2
