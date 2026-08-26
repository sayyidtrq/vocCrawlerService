from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, FetchLog, Review
from app.integrations.selenium_google_maps_client import (
    SeleniumGoogleMapsReviewClient,
)
from app.services.location_service import LocationService
from app.services.selenium_fetch_service import SeleniumFetchService
from app.utils.hashing import generate_selenium_review_hash
from app.utils.rating_parser import parse_compact_count, parse_rating


def make_settings(tmp_path):
    return Settings(
        app_env="test",
        app_name="Review System",
        log_level="INFO",
        export_dir=tmp_path / "exports",
        database_url="sqlite+pysqlite:///:memory:",
        cors_allowed_origins=("http://localhost:3000",),
        review_source_mode="selenium",
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
        analysis_batch_size=20,
        prompt_version="v1",
        page_size=20,
        show_raw_payload=False,
    )


class FakeSeleniumClient:
    source_name = "selenium_google_maps"

    def __init__(self):
        self.last_metadata = {}

    def fetch_reviews(
        self,
        location,
        limit=50,
        on_progress=None,
        date_from=None,
        date_to=None,
        keep_check=None,
        sort_by="newest",
        time_limit_seconds=0,
    ):
        self.last_metadata = {
            "target_review_count": limit,
            "loaded_review_cards": 2,
            "scraped_review_cards": 2,
            "failed_review_cards": 0,
            "scroll_attempts": 3,
            "headless": True,
            "url": location.google_reviews_url,
            "stopped_reason": "no_new_review_cards",
            "sort_applied": True,
        }
        scraped_at = datetime.now().astimezone().isoformat()
        if on_progress is not None:
            on_progress(2, limit)
        return [
            {
                "source": self.source_name,
                "external_review_id": f"review-{index}",
                "reviewer_name": name,
                "reviewer_profile_url": f"https://google.com/maps/contrib/{index}",
                "reviewer_photo_url": None,
                "reviewer_local_guide_level": (
                    "Local Guide" if index == 1 else None
                ),
                "reviewer_total_reviews": 37 if index == 1 else None,
                "rating": rating,
                "review_text": text,
                "review_relative_time": "2 minggu lalu",
                "review_time": None,
                "review_language": "id",
                "language": "id",
                "like_count": index,
                "owner_response_text": None,
                "owner_response_time": None,
                "scraped_at": scraped_at,
                "raw_payload": {"test": True},
            }
            for index, (name, rating, text) in enumerate(
                [
                    ("Andi", 5, "Pelayanan baik."),
                    ("Budi", 2, "Antrean lama."),
                ],
                start=1,
            )
        ]


class SortUnavailableSeleniumClient:
    source_name = "selenium_google_maps"

    def __init__(self):
        self.last_metadata = {}

    def fetch_reviews(
        self,
        location,
        limit=50,
        on_progress=None,
        date_from=None,
        date_to=None,
        keep_check=None,
        sort_by="newest",
        time_limit_seconds=0,
    ):
        self.last_metadata = {
            "target_review_count": limit,
            "loaded_review_cards": 4,
            "reviews_scanned": 0,
            "scraped_review_cards": 0,
            "matched_review_cards": 0,
            "failed_review_cards": 0,
            "scroll_attempts": 0,
            "headless": True,
            "url": location.google_reviews_url,
            "stopped_reason": "sort_unavailable",
            "sort_applied": False,
            "range_warning": "Date-range crawling requires newest sorting.",
        }
        return []


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed_location(session_factory, target_review_count=2):
    with session_factory() as session:
        company = Company(
            name="Test Company",
            ai_enable_flag=True,
            total_enable_review=100,
            analyze_competitor_flag=False,
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        company_id = company.id
    location = LocationService(
        company_id=company_id, session_factory=session_factory
    ).add_location(
        hospital_name="Hermina",
        branch_name="Hermina Bekasi",
        city="Bekasi",
        source="google_places",
        external_place_id="place-bekasi",
        google_reviews_url="https://www.google.com/maps/place/example/reviews",
        target_review_count=target_review_count,
        is_active=True,
    )
    return company_id, location


def test_rating_and_count_parsers():
    assert parse_rating("5 bintang") == 5
    assert parse_rating("Rating 4.0") == 4
    assert parse_rating("unknown") is None
    assert parse_compact_count("1,2k orang merasa terbantu") == 1200
    assert parse_compact_count("37 ulasan") == 37


def test_selenium_driver_uses_container_browser_and_safe_flags(
    monkeypatch, tmp_path
):
    settings = make_settings(tmp_path)
    captured = {}

    def fake_which(binary):
        return {
            "chromium": "/usr/bin/chromium",
            "chromedriver": "/usr/bin/chromedriver",
        }.get(binary)

    def fake_chrome(*, service, options):
        captured["service"] = service
        captured["options"] = options
        return object()

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.shutil.which",
        fake_which,
    )
    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.webdriver.Chrome",
        fake_chrome,
    )

    result = SeleniumGoogleMapsReviewClient(settings)._create_driver()

    assert result is not None
    assert captured["options"].binary_location == "/usr/bin/chromium"
    assert "--headless=new" in captured["options"].arguments
    assert "--no-sandbox" in captured["options"].arguments
    assert "--disable-dev-shm-usage" in captured["options"].arguments
    assert captured["service"].path == "/usr/bin/chromedriver"

def test_selenium_hash_uses_scraping_identity_fields():
    review = {
        "source": "selenium_google_maps",
        "location_id": 1,
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Pelayanan baik.",
        "review_relative_time": "2 minggu lalu",
        "reviewer_profile_url": "https://google.com/maps/contrib/1",
    }
    assert generate_selenium_review_hash(review) == generate_selenium_review_hash(
        dict(review)
    )


def test_selenium_fetch_stores_metadata_and_deduplicates(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, location = seed_location(session_factory)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=FakeSeleniumClient(),
    )

    first = service.fetch_location(location.id, target=2)
    second = service.fetch_location(location.id, target=2)

    assert first["status"] == "success"
    assert first["total_inserted"] == 2
    assert second["total_duplicate"] == 2
    with session_factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 2
        latest_log = session.scalar(
            select(FetchLog).order_by(FetchLog.id.desc()).limit(1)
        )
        assert latest_log.source == "selenium_google_maps"
        assert latest_log.metadata_json["scroll_attempts"] == 3


def test_date_range_stops_honestly_when_sort_is_unavailable(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, location = seed_location(session_factory, target_review_count=5)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=SortUnavailableSeleniumClient(),
    )

    result = service.fetch_location(
        location.id,
        target=5,
        date_from=datetime.now().astimezone() - timedelta(days=7),
    )

    assert result["status"] == "partial_success"
    assert result["total_inserted"] == 0
    assert result["total_fetched"] == 0
    assert result["metadata"]["stopped_reason"] == "sort_unavailable"
    assert result["metadata"]["reviews_scanned"] == 0
    assert "range_warning" in result["metadata"]


def test_date_range_with_only_out_of_range_reviews_is_partial(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, location = seed_location(session_factory)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=FakeSeleniumClient(),
    )

    result = service.fetch_location(
        location.id,
        target=2,
        date_from=datetime.now().astimezone() - timedelta(days=1),
    )

    assert result["status"] == "success"
    assert result["total_fetched"] == 2
    assert result["total_inserted"] == 0
    assert result["total_skipped_out_of_range"] == 2
