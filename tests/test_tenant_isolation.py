from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Company
from app.services.competitor_service import CompetitorService
from app.services.entitlement_service import EntitlementService
from app.services.fetch_log_service import FetchLogService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.utils.hashing import generate_review_hash


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
def two_companies(session_factory):
    with session_factory() as session:
        company_a = Company(
            name="Company A",
            ai_enable_flag=True,
            total_enable_review=100,
            analyze_competitor_flag=True,
        )
        company_b = Company(
            name="Company B",
            ai_enable_flag=False,
            total_enable_review=50,
            analyze_competitor_flag=False,
        )
        session.add_all([company_a, company_b])
        session.commit()
        session.refresh(company_a)
        session.refresh(company_b)
        return company_a.id, company_b.id


def _add_location(session_factory, company_id: int, external_place_id: str):
    return LocationService(company_id=company_id, session_factory=session_factory).add_location(
        hospital_name="Hermina",
        branch_name=f"Branch {external_place_id}",
        source="google_places",
        external_place_id=external_place_id,
        is_active=True,
    )


def test_location_isolation(session_factory, two_companies):
    company_a_id, company_b_id = two_companies
    location_a = _add_location(session_factory, company_a_id, "place-a")
    _add_location(session_factory, company_b_id, "place-b")

    service_a = LocationService(company_id=company_a_id, session_factory=session_factory)
    locations_a = service_a.get_all_locations()
    assert [loc.external_place_id for loc in locations_a] == ["place-a"]

    service_b = LocationService(company_id=company_b_id, session_factory=session_factory)
    # Company B cannot read, update, or delete Company A's location.
    assert service_b.get_location(location_a.id) is None
    with pytest.raises(ValueError):
        service_b.update_location(location_a.id, "branch_name", "Hijacked")
    with pytest.raises(ValueError):
        service_b.delete_location(location_a.id)


def test_review_isolation(session_factory, two_companies):
    company_a_id, company_b_id = two_companies
    location_a = _add_location(session_factory, company_a_id, "place-a")

    review_data = {
        "location_id": location_a.id,
        "source": "google_places",
        "external_place_id": "place-a",
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Bagus",
        "review_time": datetime.fromisoformat("2026-06-19T09:00:00+07:00"),
    }
    review_data["review_hash"] = generate_review_hash(review_data)

    review_service_a = ReviewService(company_id=company_a_id, session_factory=session_factory)
    inserted, duplicate = review_service_a.insert_review(dict(review_data))
    assert duplicate is False
    assert inserted.company_id == company_a_id

    # Company B's ReviewService must not see Company A's review.
    review_service_b = ReviewService(company_id=company_b_id, session_factory=session_factory)
    items_b, total_b = review_service_b.get_reviews()
    assert total_b == 0
    assert items_b == []
    assert review_service_b.get_review(inserted.id) is None

    items_a, total_a = review_service_a.get_reviews()
    assert total_a == 1
    assert items_a[0]["id"] == inserted.id


def test_competitor_isolation(session_factory, two_companies):
    company_a_id, company_b_id = two_companies
    competitor_service_a = CompetitorService(company_id=company_a_id, session_factory=session_factory)
    competitor_a = competitor_service_a.add_competitor(
        name="RS Kompetitor A",
        source="apify",
        external_place_id="comp-a",
    )

    competitor_service_b = CompetitorService(company_id=company_b_id, session_factory=session_factory)
    assert competitor_service_b.get_competitor(competitor_a.id) is None
    with pytest.raises(ValueError):
        competitor_service_b.update_competitor(competitor_a.id, "name", "Hijacked")
    with pytest.raises(ValueError):
        competitor_service_b.delete_competitor(competitor_a.id)

    assert [c.id for c in competitor_service_a.get_all_competitors()] == [competitor_a.id]
    assert competitor_service_b.get_all_competitors() == []


def test_fetch_log_isolation(session_factory, two_companies):
    company_a_id, company_b_id = two_companies
    location_a = _add_location(session_factory, company_a_id, "place-a")

    log_service_a = FetchLogService(company_id=company_a_id, session_factory=session_factory)
    log_service_a.start_log(location_a.id, "google_places", {})

    log_service_b = FetchLogService(company_id=company_b_id, session_factory=session_factory)
    assert log_service_b.get_logs() == []
    assert len(log_service_a.get_logs()) == 1


def test_entitlement_flags_are_per_company(session_factory, two_companies):
    company_a_id, company_b_id = two_companies

    entitlement_a = EntitlementService(company_a_id, session_factory=session_factory)
    entitlement_b = EntitlementService(company_b_id, session_factory=session_factory)

    entitlement_a.require_ai_enabled()  # must not raise
    entitlement_a.require_competitor_enabled()  # must not raise

    with pytest.raises(Exception):
        entitlement_b.require_ai_enabled()
    with pytest.raises(Exception):
        entitlement_b.require_competitor_enabled()

    assert entitlement_a.review_quota() == 100
    assert entitlement_b.review_quota() == 50
    assert entitlement_b.clamp_review_target(300) == 50
    assert entitlement_a.clamp_review_target(30) == 30
