"""Integration test verifying Crawler Service for both:
1. Full Pipeline & Two-segment OneBox pipeline (Fetch -> Analyze)
2. Standalone AI Analysis (single review rerun & pending batch analysis)
using the exact same APIs that OneBox uses.
"""

from __future__ import annotations

import json
from unittest.mock import patch

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
from app.integrations.jev_client import JevAiClient
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
def crawler_test_env(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        company = Company(name="Hermina Hospital Group", ai_enable_flag=True)
        session.add(company)
        session.flush()

        location = Location(
            company_id=company.id,
            hospital_name="RS Hermina",
            branch_name="Bekasi",
            source="apify_google_maps",
            external_place_id="place-bekasi-1",
            ai_enabled=True,
        )
        session.add(location)
        session.flush()

        # Add 2 sample reviews
        r1 = Review(
            company_id=company.id,
            location_id=location.id,
            source="apify_google_maps",
            external_place_id="place-bekasi-1",
            external_review_id="review-bekasi-1",
            reviewer_name="Budi Santoso",
            rating=1,
            review_text="Pelayanan perawat ketus dan antrean obat lama sekali.",
            review_hash="hash-bekasi-1",
            raw_payload={},
        )
        r2 = Review(
            company_id=company.id,
            location_id=location.id,
            source="apify_google_maps",
            external_place_id="place-bekasi-1",
            external_review_id="review-bekasi-2",
            reviewer_name="Siti Rahma",
            rating=5,
            review_text="Dokter spesialis anak sangat sabar dan teliti.",
            review_hash="hash-bekasi-2",
            raw_payload={},
        )
        session.add_all([r1, r2])
        session.commit()
        company_id = company.id
        location_id = location.id
        review_1_id = r1.id
        review_2_id = r2.id

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        analysis_provider="absa",
        analysis_batch_size=10,
        analysis_llm_concurrency=1,
        analysis_llm_max_retries=0,
        jev_base_url="https://jev.mock.test/api",
        jev_api_key="test-jev-key",
    )

    absa_calls = []
    jev_calls = []

    def mock_absa_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/inference/engines"):
            return httpx.Response(
                200,
                json={"engines": [{"id": "v14", "available": True}]},
            )
        data = json.loads(request.content)
        absa_calls.append(data)
        return httpx.Response(
            200,
            json={
                "engine_version": "v14",
                "model_version": "14.0.0-candidate",
                "results": [
                    {
                        "aspect": "antrean obat",
                        "opinion": "lama sekali",
                        "sentiment": "negative",
                        "taxonomy": "Waiting Time",
                        "confidence": 0.95,
                    },
                    {
                        "aspect": "perawat",
                        "opinion": "ketus",
                        "sentiment": "negative",
                        "taxonomy": "Nurse",
                        "confidence": 0.90,
                    },
                ],
            },
        )

    def mock_jev_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        jev_calls.append(data)
        text = data.get("state", "")
        is_neg = "ketus" in text or "lama" in text
        return httpx.Response(
            200,
            json={
                "answers": {
                    "sentiment": {
                        "choice": "negative" if is_neg else "positive",
                        "probabilities": {
                            "negative": 0.92 if is_neg else 0.05,
                            "positive": 0.05 if is_neg else 0.95,
                            "neutral": 0.03,
                            "mixed": 0.0,
                        },
                        "confidence": 0.92 if is_neg else 0.95,
                    },
                    "category": {
                        "choice": "waiting time" if is_neg else "doctor",
                        "probabilities": {"waiting time": 0.88, "doctor": 0.12},
                        "confidence": 0.88,
                    },
                    "is_safety_issue": {"noul": 0.05},
                    "is_viral_risk": {"noul": 0.85 if is_neg else 0.10},
                }
            },
        )

    absa_http = httpx.Client(
        base_url="http://absa.mock.test/api",
        transport=httpx.MockTransport(mock_absa_handler),
    )
    jev_http = httpx.Client(
        base_url="https://jev.mock.test/api",
        transport=httpx.MockTransport(mock_jev_handler),
    )

    monkeypatch.setattr(analysis_service_module, "get_settings", lambda: settings)
    monkeypatch.setattr(analysis_service_module, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(
        analysis_client_module,
        "AbsaClient",
        lambda active_settings: AbsaClient(active_settings, http_client=absa_http),
    )
    monkeypatch.setattr(
        analysis_client_module,
        "JevAiClient",
        lambda active_settings: JevAiClient(active_settings, http_client=jev_http),
    )

    principal = ServicePrincipal(
        client_id=company_id,
        key_id="onebox-integration-key",
        company_id=company_id,
        scopes=frozenset({"analysis:write", "reviews:read"}),
    )

    def _override_db():
        with session_factory() as session:
            yield session

    from apps.api.app_api.dependencies import get_db_session

    app = create_app()
    app.dependency_overrides[get_integration_analysis_session_factory] = (
        lambda: session_factory
    )
    app.dependency_overrides[get_integration_session_factory] = lambda: session_factory
    app.dependency_overrides[require_service_principal] = lambda: principal
    app.dependency_overrides[get_db_session] = _override_db

    client = TestClient(app)
    yield {
        "client": client,
        "session_factory": session_factory,
        "company_id": company_id,
        "location_id": location_id,
        "review_1_id": review_1_id,
        "review_2_id": review_2_id,
        "absa_calls": absa_calls,
        "jev_calls": jev_calls,
    }

    absa_http.close()
    jev_http.close()


def test_ai_analysis_default_fallback_to_absa(crawler_test_env):
    """OneBox default fallback to ABSA when no provider or provider=absa is sent."""
    client = crawler_test_env["client"]
    absa_calls = crawler_test_env["absa_calls"]

    # Call /api/integration/v1/analysis/pending with no provider (OneBox default fallback)
    resp = client.post(
        "/api/integration/v1/analysis/pending",
        json={"location_id": crawler_test_env["location_id"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] >= 1
    assert len(absa_calls) >= 1
    assert "antrean obat" in str(absa_calls[0]) or "ketus" in str(absa_calls[0])


def test_ai_analysis_single_review_with_jev(crawler_test_env):
    """OneBox single-review manual analysis calling Crawler JEV AI endpoint."""
    client = crawler_test_env["client"]
    review_id = crawler_test_env["review_1_id"]
    jev_calls = crawler_test_env["jev_calls"]

    # Call /api/integration/v1/analysis/reviews/{id}/rerun?provider=jev
    resp = client.post(
        f"/api/integration/v1/analysis/reviews/{review_id}/rerun?provider=jev"
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["success"] == 1
    assert len(jev_calls) == 1
    assert "Pelayanan perawat ketus" in jev_calls[0]["state"]

    # Verify review was updated with JEV AI results
    review_resp = client.get("/api/integration/v1/reviews")
    assert review_resp.status_code == 200
    r1 = next(item for item in review_resp.json()["data"] if item["id"] == review_id)
    assert r1["analyzed"] is True
    assert r1["analysis_status"] == "completed"
    assert r1["sentiment"] == "negative"
    assert r1["sentiment_score"] == 0.92
    assert r1["issue_category"] == "waiting_time"
    assert r1["urgency"] == "high"


def test_ai_analysis_batch_pending_with_jev(crawler_test_env):
    """OneBox batch analysis button calling Crawler with provider=jev."""
    client = crawler_test_env["client"]
    jev_calls = crawler_test_env["jev_calls"]

    # Call /api/integration/v1/analysis/pending with {"provider": "jev"}
    resp = client.post(
        "/api/integration/v1/analysis/pending",
        json={
            "location_id": crawler_test_env["location_id"],
            "provider": "jev",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] == 2
    assert len(jev_calls) == 2


def test_two_segment_pipeline_onebox_flow(crawler_test_env):
    """Test the 2-segment pipeline mechanism:
    Segment 1: Fetch/Import reviews (GET /api/integration/v1/reviews)
    Segment 2: AI Analysis (POST /api/integration/v1/analysis/pending)
    """
    client = crawler_test_env["client"]
    location_id = crawler_test_env["location_id"]

    # SEGMENT 1: OneBox fetch/import reviews
    seg1_resp = client.get(
        f"/api/integration/v1/reviews?location_id={location_id}"
    )
    assert seg1_resp.status_code == 200
    reviews = seg1_resp.json()["data"]
    assert len(reviews) == 2
    assert all("external_review_id" in r for r in reviews)

    # SEGMENT 2: OneBox triggers AI analysis separately
    seg2_resp = client.post(
        "/api/integration/v1/analysis/pending",
        json={"location_id": location_id, "provider": "jev"},
    )
    assert seg2_resp.status_code == 200
    assert seg2_resp.json()["data"]["success"] == 2

    # Verify reviews reflect completed analysis
    seg1_updated = client.get(
        f"/api/integration/v1/reviews?location_id={location_id}"
    )
    assert seg1_updated.status_code == 200
    for r in seg1_updated.json()["data"]:
        assert r["analyzed"] is True
        assert r["analysis_status"] == "completed"


def test_crawler_location_pipeline_with_jev(crawler_test_env):
    """Test the Crawler Location Pipeline endpoint (/pipeline/location) with Jev AI."""
    client = crawler_test_env["client"]
    location_id = crawler_test_env["location_id"]

    resp = client.post(
        "/api/pipeline/location",
        json={
            "location_id": location_id,
            "fetch": False,
            "analyze": True,
            "provider": "jev",
        },
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"
    assert "analysis" in res["steps"]
    assert res["steps"]["analysis"]["success"] >= 1


def test_crawler_model_discovery(crawler_test_env):
    """Test AI model discovery endpoint (/api/integration/v1/analysis/models) for both absa and jev."""
    client = crawler_test_env["client"]

    # Discovery for ABSA
    absa_resp = client.get("/api/integration/v1/analysis/models?provider=absa")
    assert absa_resp.status_code == 200
    absa_data = absa_resp.json()["data"]
    assert absa_data["provider"] == "absa"
    assert len(absa_data["models"]) >= 1

    # Discovery for JEV
    jev_resp = client.get("/api/integration/v1/analysis/models?provider=jev")
    assert jev_resp.status_code == 200
    jev_data = jev_resp.json()["data"]
    assert jev_data["provider"] == "jev"
    assert len(jev_data["models"]) >= 1
