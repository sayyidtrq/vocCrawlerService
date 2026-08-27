from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Company, Location, Review, ReviewAnalysis
from app.services.analysis_service import RATING_FALLBACK_MODEL
from apps.api.app_api.routers import integration_analysis as integration_analysis_router
from apps.api.app_api.routers.integration_analysis import (
    get_integration_analysis_session_factory,
)
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app


def make_database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        companies = [
            Company(name="Tenant A", ai_enable_flag=True),
            Company(name="Tenant B", ai_enable_flag=True),
        ]
        session.add_all(companies)
        session.flush()
        locations = [
            Location(
                company_id=companies[0].id,
                hospital_name="Hospital A",
                branch_name="Branch A",
                source="selenium_google_maps",
                external_place_id="place-a",
                ai_enabled=True,
            ),
            Location(
                company_id=companies[1].id,
                hospital_name="Hospital B",
                branch_name="Branch B",
                source="selenium_google_maps",
                external_place_id="place-b",
                ai_enabled=True,
            ),
        ]
        session.add_all(locations)
        session.flush()
        session.add_all(
            [
                Review(
                    company_id=companies[0].id,
                    location_id=locations[0].id,
                    source="selenium_google_maps",
                    external_review_id="review-a",
                    rating=1,
                    review_text="",
                    review_hash="hash-a",
                    raw_payload={},
                ),
                Review(
                    company_id=companies[1].id,
                    location_id=locations[1].id,
                    source="selenium_google_maps",
                    external_review_id="review-b",
                    rating=1,
                    review_text="",
                    review_hash="hash-b",
                    raw_payload={},
                ),
            ]
        )
        session.commit()
    return factory


def principal(company_id: int, scopes=("analysis:write",)) -> ServicePrincipal:
    return ServicePrincipal(
        client_id=company_id,
        key_id=f"key-{company_id}",
        company_id=company_id,
        scopes=frozenset(scopes),
    )


def make_client(session_factory, current_principal: ServicePrincipal) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_integration_analysis_session_factory] = (
        lambda: session_factory
    )
    app.dependency_overrides[require_service_principal] = lambda: current_principal
    return TestClient(app)


def test_service_token_runs_analysis_only_for_its_tenant():
    factory = make_database()
    client = make_client(factory, principal(1))

    response = client.post("/api/integration/v1/analysis/pending", json={})

    assert response.status_code == 200
    assert response.json()["data"]["success"] == 1
    with factory() as session:
        analyses = list(session.scalars(select(ReviewAnalysis)))
        status_by_company = dict(
            session.execute(
                select(Review.company_id, Review.analysis_status)
            ).all()
        )
    assert len(analyses) == 1
    assert analyses[0].model_name == RATING_FALLBACK_MODEL
    assert status_by_company == {1: "completed", 2: "pending"}


def test_service_token_cannot_rerun_another_tenants_review():
    factory = make_database()
    client = make_client(factory, principal(1))

    response = client.post("/api/integration/v1/analysis/reviews/2/rerun")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REVIEW_NOT_FOUND"


def test_failed_single_review_rerun_is_not_reported_as_http_success(monkeypatch):
    factory = make_database()
    client = make_client(factory, principal(1))

    monkeypatch.setattr(
        integration_analysis_router.AnalysisService,
        "rerun_review",
        lambda self, review_id: {
            "total": 1,
            "success": 0,
            "failed": 1,
            "errors": [{"review_id": review_id, "error": "Analysis failed."}],
        },
    )

    response = client.post("/api/integration/v1/analysis/reviews/1/rerun")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ANALYSIS_FAILED"


def test_service_token_lists_models_from_the_active_provider(monkeypatch):
    factory = make_database()
    client = make_client(factory, principal(1))
    monkeypatch.setattr(
        integration_analysis_router.LocalLLMClient,
        "list_models",
        lambda self: ["model-a", "model-b:latest"],
    )

    response = client.get("/api/integration/v1/analysis/models")

    assert response.status_code == 200
    assert response.json()["data"]["models"] == ["model-a", "model-b:latest"]
    assert response.json()["data"]["default_model"]


def test_analysis_scope_is_required():
    factory = make_database()
    client = make_client(factory, principal(1, scopes=("crawl:enqueue",)))

    response = client.post("/api/integration/v1/analysis/pending", json={})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_service_token_can_monitor_and_rollback_its_analysis():
    factory = make_database()
    client = make_client(factory, principal(1))
    assert client.post("/api/integration/v1/analysis/pending", json={}).status_code == 200

    quality = client.get("/api/integration/v1/analysis/quality-summary?hours=24")
    rollback = client.post(
        "/api/integration/v1/analysis/rollback",
        json={"model_name": RATING_FALLBACK_MODEL},
    )

    assert quality.status_code == 200
    assert quality.json()["data"]["by_status"]["completed"] == 1
    assert rollback.status_code == 200
    assert rollback.json()["data"]["reviews_affected"] == 1
    with factory() as session:
        assert session.scalar(select(func.count(ReviewAnalysis.id))) == 0
