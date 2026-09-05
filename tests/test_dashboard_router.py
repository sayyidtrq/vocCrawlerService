from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Company, Location, Review, ReviewAnalysis
from apps.api.app_api.dependencies import get_db_session
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app


@pytest.fixture()
def seeded():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        company = Company(name="Dashboard Wiring Co")
        session.add(company)
        session.commit()
        session.refresh(company)

        location = Location(
            company_id=company.id,
            hospital_name="Hermina",
            branch_name="Hermina Bekasi",
            source="google_maps",
            external_place_id="place-dashboard-wiring",
        )
        session.add(location)
        session.commit()
        session.refresh(location)

        review = Review(
            company_id=company.id,
            location_id=location.id,
            source="google_maps",
            review_text="Pelayanan lambat.",
            rating=2,
            review_hash="hash-dashboard-wiring-1",
        )
        session.add(review)
        session.commit()
        session.refresh(review)

        session.add(
            ReviewAnalysis(
                review_id=review.id,
                sentiment="negative",
                issue_category="waiting_time",
                urgency="high",
                recommended_action="Tambah loket.",
            )
        )
        session.commit()

        company_id, location_id = company.id, location.id

    application = create_app()
    application.dependency_overrides[require_service_principal] = (
        lambda: ServicePrincipal(
            client_id=1, key_id="test", company_id=company_id, scopes=frozenset()
        )
    )

    def override_get_db_session():
        with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_get_db_session
    return {
        "client": TestClient(application),
        "company_id": company_id,
        "location_id": location_id,
    }


def test_dashboard_overview_uses_injected_session(seeded):
    response = seeded["client"].get("/api/dashboard/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["total_locations"] == 1
    assert body["total_reviews"] == 1
    assert body["critical_issues"] == 1


def test_dashboard_location_summary_uses_injected_session(seeded):
    response = seeded["client"].get(
        f"/api/dashboard/locations/{seeded['location_id']}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["location_name"] == "Hermina Bekasi"
    assert body["sentiments"]["negative"] == 1


def test_dashboard_critical_issues_uses_injected_session(seeded):
    response = seeded["client"].get("/api/dashboard/critical-issues")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_dashboard_negative_reviews_uses_injected_session(seeded):
    response = seeded["client"].get("/api/dashboard/negative-reviews")
    assert response.status_code == 200
    assert response.json()["total"] == 1
