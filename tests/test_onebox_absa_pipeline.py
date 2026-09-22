"""OneBox -> crawler -> ABSA -> crawler -> OneBox contract test."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, Location, Review, ReviewAnalysis
from app.integrations import analysis_client as analysis_client_module
from app.integrations.absa_client import AbsaClient
from app.services import analysis_service as analysis_service_module
from apps.api.app_api.routers.integration_analysis import (
    get_integration_analysis_session_factory,
)
from apps.api.app_api.routers.integration_reviews import (
    get_integration_session_factory,
)
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app


@pytest.fixture()
def pipeline(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        company = Company(name="Hermina", ai_enable_flag=True)
        session.add(company)
        session.flush()
        location = Location(
            company_id=company.id,
            hospital_name="Hermina",
            branch_name="Depok",
            source="apify_google_maps",
            external_place_id="place-depok",
            ai_enabled=True,
        )
        session.add(location)
        session.flush()
        session.add(
            Review(
                company_id=company.id,
                location_id=location.id,
                source="apify_google_maps",
                external_place_id="place-depok",
                external_review_id="review-1",
                reviewer_name="Patient",
                rating=2,
                review_text="Dokternya ramah tetapi antreannya lama.",
                review_hash="review-hash-1",
                raw_payload={},
            )
        )
        session.commit()
        company_id = company.id

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        analysis_provider="absa",
        analysis_batch_size=1,
        analysis_llm_concurrency=1,
        analysis_llm_max_retries=0,
    )
    absa_requests = []

    def absa_handler(request: httpx.Request) -> httpx.Response:
        absa_requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "engine_version": "v14",
                "model_version": "14.0.0-candidate",
                "results": [
                    {
                        "aspect": "dokter",
                        "opinion": "ramah",
                        "sentiment": "positive",
                        "taxonomy": "Doctor",
                        "confidence": 0.88,
                    },
                    {
                        "aspect": "antrean",
                        "opinion": "lama",
                        "sentiment": "negative",
                        "taxonomy": "Waiting Time",
                        "confidence": 0.93,
                    },
                ],
            },
        )

    absa_http = httpx.Client(
        base_url="http://absa.test/api",
        transport=httpx.MockTransport(absa_handler),
    )
    monkeypatch.setattr(analysis_service_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        analysis_client_module,
        "AbsaClient",
        lambda active_settings: AbsaClient(
            active_settings,
            http_client=absa_http,
        ),
    )

    principal = ServicePrincipal(
        client_id=company_id,
        key_id="onebox-test",
        company_id=company_id,
        scopes=frozenset({"analysis:write", "reviews:read"}),
    )
    app = create_app()
    app.dependency_overrides[get_integration_analysis_session_factory] = (
        lambda: session_factory
    )
    app.dependency_overrides[get_integration_session_factory] = lambda: session_factory
    app.dependency_overrides[require_service_principal] = lambda: principal

    yield TestClient(app), session_factory, absa_requests
    absa_http.close()


@pytest.mark.parametrize("analysis_request", [{}, {"provider": "absa"}])
def test_onebox_receives_absa_sentiment(analysis_request, pipeline):
    client, session_factory, absa_requests = pipeline

    analysis = client.post(
        "/api/integration/v1/analysis/pending",
        json=analysis_request,
    )
    reviews = client.get("/api/integration/v1/reviews")

    assert analysis.status_code == 200
    assert analysis.json()["data"]["success"] == 1
    assert absa_requests == [
        {
            "review": "Dokternya ramah tetapi antreannya lama.",
            "engine_version": "v14",
            "profile": "maps_high_recall",
            "confidence_threshold": 0.1,
        }
    ]
    assert reviews.status_code == 200
    item = reviews.json()["data"][0]
    assert item["analysis_status"] == "completed"
    assert item["analyzed"] is True
    assert item["sentiment"] == "mixed"
    assert item["sentiment_score"] == 0.93
    assert item["issue_category"] == "waiting_time"
    assert item["urgency"] == "medium"
    assert item["keywords"] == ["dokter", "ramah", "antrean", "lama"]

    with session_factory() as session:
        stored = session.scalar(select(ReviewAnalysis))
    assert stored.model_name == "v14"
    assert stored.raw_response["absa"]["model_version"] == "14.0.0-candidate"
