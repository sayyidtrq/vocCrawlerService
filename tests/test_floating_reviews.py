"""Floating reviews, crawl coverage, and the OneBox review quota (spec CS-7, CS-5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, CrawlWindowLog, Location, Review
from app.integrations.apify_review_client import ApifyRunIncompleteError
from app.services.apify_fetch_service import ApifyFetchService
from app.services.fetch_service import FetchService
from app.services.review_service import ReviewService
from app.utils.date_parser import is_within_date_range_approx, relative_time_precision

SCRAPED = datetime(2026, 9, 15, 7, tzinfo=timezone.utc)


def make_db():
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
        location = Location(
            company_id=company.id,
            hospital_name="Hermina",
            branch_name="Hermina Bekasi",
            source="apify_google_maps",
            external_place_id="place-1",
            onebox_location_id=101,
        )
        session.add(location)
        session.commit()
        return factory, company.id, location


def utc(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def raw(review_id, *, text="Baik.", rating=5, when="2026-09-14T00:00:00Z",
        relative="a day ago", precision="day", edited=False, name=None):
    return {
        "source": "apify_google_maps",
        "external_place_id": "place-1",
        "external_review_id": review_id,
        "reviewer_name": name,
        "rating": rating,
        "review_text": text,
        "review_time": when,
        "review_time_precision": precision,
        "is_edited": edited,
        "edited_at": when if edited else None,
        "review_relative_time": relative,
        "scraped_at": SCRAPED.isoformat(),
        "raw_payload": {"id": review_id},
    }


def store(factory, company_id, location, raw_review):
    """Lewat jalur normalize yang sebenarnya, bukan dict buatan tangan."""
    normalized = FetchService(
        company_id=company_id,
        session_factory=factory,
        settings=Settings(database_url="sqlite+pysqlite:///:memory:"),
        client=object(),
    ).normalize_review(location, raw_review)
    return ReviewService(company_id=company_id, session_factory=factory).insert_review(
        normalized
    )


def only_review(factory):
    with factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 1
        return session.scalar(select(Review))


# --------------------------------------------------------------- parser rules


def test_relative_time_precision_units():
    cases = {
        "a day ago": "day",
        "2 days ago": "day",
        "5 hours ago": "day",
        "a week ago": "week",
        "3 weeks ago": "week",
        "a month ago": "month",
        "11 months ago": "month",
        "a year ago": "year",
        "6 years ago": "year",
        "Edited 2 months ago": "month",
        "": "unknown",
        None: "unknown",
        "garbage": "unknown",
    }
    for text, expected in cases.items():
        assert relative_time_precision(text) == expected, text


def test_non_multiple_age_means_the_actor_had_a_real_date():
    exact = datetime(2026, 4, 23, tzinfo=timezone.utc)  # 145 days, "4 months ago"
    estimated = SCRAPED.replace(hour=0) - timedelta(days=120)
    assert relative_time_precision("4 months ago", exact, SCRAPED) == "day"
    assert relative_time_precision("4 months ago", estimated, SCRAPED) == "month"


def test_year_precision_review_is_kept_by_an_older_window():
    stamped = datetime(2025, 9, 15, tzinfo=timezone.utc)  # "a year ago"
    window = (
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 3, 31, tzinfo=timezone.utc),
    )
    assert is_within_date_range_approx(stamped, "year", *window)
    assert not is_within_date_range_approx(stamped, "day", *window)


# -------------------------------------------------------------- re-sightings


def test_anonymous_placeholder_is_replaced_through_the_real_normalize_path():
    factory, company_id, location = make_db()
    store(factory, company_id, location, raw("r1", name=None))
    assert only_review(factory).reviewer_name == "Anonymous"

    _, duplicate = store(factory, company_id, location, raw("r1", name="Andi"))

    assert duplicate is True
    assert only_review(factory).reviewer_name == "Andi"


def test_precise_date_is_not_overwritten_by_a_coarser_sighting():
    factory, company_id, location = make_db()
    store(factory, company_id, location, raw("r1", when="2025-09-10T00:00:00Z"))

    store(
        factory,
        company_id,
        location,
        raw("r1", when="2025-09-15T00:00:00Z", relative="a year ago", precision="year"),
    )

    review = only_review(factory)
    assert utc(review.review_time) == datetime(2025, 9, 10, tzinfo=timezone.utc)
    assert review.review_time_precision == "day"


def test_legacy_row_without_precision_keeps_its_date():
    factory, company_id, location = make_db()
    store(
        factory,
        company_id,
        location,
        raw("r1", when="2025-09-15T00:00:00Z", relative="a year ago", precision=None),
    )
    later = SCRAPED + timedelta(days=5)

    store(
        factory,
        company_id,
        location,
        {
            **raw(
                "r1",
                when="2025-09-20T00:00:00Z",
                relative="a year ago",
                precision="year",
            ),
            "scraped_at": later.isoformat(),
        },
    )

    review = only_review(factory)
    # Derived "year" from its own data, so the equally coarse sighting loses.
    assert utc(review.review_time) == datetime(2025, 9, 15, tzinfo=timezone.utc)
    assert review.review_time_precision == "year"


def test_edited_review_updates_in_place_and_keeps_identity():
    factory, company_id, location = make_db()
    store(factory, company_id, location, raw("r1", text="Bagus sekali", rating=5))
    before = only_review(factory)
    original_hash, original_time = before.review_hash, before.review_time
    watermark = before.sync_updated_at
    with factory() as session:
        session.get(Review, before.id).analysis_status = "completed"
        session.commit()

    _, duplicate = store(
        factory,
        company_id,
        location,
        raw(
            "r1",
            text="Ternyata buruk",
            rating=1,
            when="2026-09-10T00:00:00Z",
            relative="Edited 5 days ago",
            edited=True,
        ),
    )

    after = only_review(factory)
    assert duplicate is True
    assert after.review_text == "Ternyata buruk"
    assert after.rating == 1
    assert after.is_edited is True
    assert utc(after.edited_at) == datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert after.review_hash == original_hash
    assert after.review_time == original_time
    assert after.analysis_status == "pending"
    assert after.sync_updated_at > watermark
    assert after.raw_payload["previous_versions"][0]["rating"] == 5


# ------------------------------------------------------ coverage and windows


class ScriptedClient:
    source_name = "apify_google_maps"

    def __init__(self, reviews, *, expected=None, incomplete=False):
        self.reviews = reviews
        self.expected = expected
        self.incomplete = incomplete
        self.last_metadata = {}
        self.calls = []

    def fetch_reviews(self, crawl_target, limit, sort_by="newest", date_from=None, date_to=None):
        self.calls.append({"limit": limit, "date_from": date_from})
        self.last_metadata = {
            "expected_review_count": self.expected,
            "collected_unique": len(self.reviews),
            "failed_review_cards": 0,
        }
        if self.incomplete:
            raise ApifyRunIncompleteError(
                "not confirmed", reviews=list(self.reviews), code="APIFY_RUN_FAILED"
            )
        return list(self.reviews)


def service(factory, company_id, client):
    return ApifyFetchService(
        company_id=company_id,
        session_factory=factory,
        settings=Settings(database_url="sqlite+pysqlite:///:memory:"),
        client=client,
    )


def location_row(factory, location_id):
    with factory() as session:
        return session.get(Location, location_id)


def test_successful_delta_moves_the_crawler_cursor():
    factory, company_id, location = make_db()
    client = ScriptedClient([raw("r1", when="2026-09-14T00:00:00Z")])

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="delta"
    )

    row = location_row(factory, location.id)
    assert result["status"] == "success"
    assert utc(row.newest_crawled_at) == datetime(2026, 9, 14, tzinfo=timezone.utc)
    assert row.newest_crawled_precision == "day"
    assert result["metadata"]["coverage_state"]["newest_crawled_at"].startswith(
        "2026-09-14"
    )


def test_delta_ignores_a_stale_onebox_cursor():
    factory, company_id, location = make_db()
    now = datetime.now(timezone.utc)
    with factory() as session:
        row = session.get(Location, location.id)
        row.newest_crawled_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        row.last_sweep_at = now  # sweep not due
        session.commit()
    client = ScriptedClient([])

    result = service(factory, company_id, client).fetch_location(
        location.id,
        coverage="delta",
        date_from=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )

    assert client.calls[0]["date_from"] == datetime(2026, 9, 13, tzinfo=timezone.utc)
    assert result["metadata"]["safety_sweep"] is False


def test_due_safety_sweep_widens_the_delta_window():
    factory, company_id, location = make_db()
    with factory() as session:
        row = session.get(Location, location.id)
        row.newest_crawled_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
        row.last_sweep_at = None
        session.commit()
    client = ScriptedClient([])

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="delta"
    )

    assert client.calls[0]["date_from"] == datetime(2026, 8, 15, tzinfo=timezone.utc)
    assert result["metadata"]["safety_sweep"] is True
    assert location_row(factory, location.id).last_sweep_at is not None


def test_incomplete_run_does_not_move_the_cursor():
    factory, company_id, location = make_db()
    client = ScriptedClient([raw("r1", when="2026-09-14T00:00:00Z")], incomplete=True)

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="delta"
    )

    assert result["status"] == "failed"
    assert result["metadata"]["stop_reason"] == "source_not_confirmed"
    assert location_row(factory, location.id).newest_crawled_at is None


def test_date_window_never_moves_the_delta_cursor_and_is_logged():
    factory, company_id, location = make_db()
    client = ScriptedClient(
        [
            raw("r1", when="2026-09-14T00:00:00Z"),
            raw("r2", when="2025-02-10T00:00:00Z"),
        ]
    )
    window = (
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 3, 31, tzinfo=timezone.utc),
    )

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="date_window", date_from=window[0], date_to=window[1]
    )

    row = location_row(factory, location.id)
    assert result["total_inserted"] == 1
    assert row.newest_crawled_at is None
    assert utc(row.oldest_crawled_at) == datetime(2025, 2, 10, tzinfo=timezone.utc)
    with factory() as session:
        log = session.scalar(select(CrawlWindowLog))
        assert log.completeness == "complete"
        assert log.location_id == location.id


def test_complete_backfill_is_recorded():
    factory, company_id, location = make_db()
    client = ScriptedClient([raw("r1"), raw("r2")], expected=2)

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="full_backfill"
    )

    row = location_row(factory, location.id)
    assert result["metadata"]["completeness"] == "complete"
    assert row.backfill_completed_at is not None
    assert row.last_expected_review_count == 2


# ---------------------------------------------------------------- quota (CS-5)


def test_review_quota_stops_new_rows_but_not_duplicates():
    factory, company_id, location = make_db()
    store(factory, company_id, location, raw("old"))
    client = ScriptedClient([raw("new-1"), raw("old", name="Andi"), raw("new-2")])

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="delta", review_quota_remaining=1
    )

    assert result["total_inserted"] == 1
    assert result["total_duplicate"] == 1
    assert result["status"] == "partial_success"
    assert result["metadata"]["stop_reason"] == "review_quota_exhausted"
    assert result["metadata"]["skipped_quota"] == 1
    with factory() as session:
        names = {
            row[0]: row[1]
            for row in session.execute(
                select(Review.external_review_id, Review.reviewer_name)
            )
        }
    assert names["old"] == "Andi"  # the free duplicate still carried its repair
    assert "new-2" not in names


def test_no_quota_means_unlimited():
    factory, company_id, location = make_db()
    client = ScriptedClient([raw("a"), raw("b")])

    result = service(factory, company_id, client).fetch_location(
        location.id, coverage="delta", review_quota_remaining=None
    )

    assert result["total_inserted"] == 2
    assert result["metadata"]["stop_reason"] != "review_quota_exhausted"
