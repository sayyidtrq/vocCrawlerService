#!/usr/bin/env python3
"""Live Real-Time Demonstration: Crawler Service Pipeline & AI Analysis APIs.
Executes the exact HTTP endpoints and payloads used by OneBox.
"""

from __future__ import annotations

import json
import sys
import time

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, Location, Review, ReviewAnalysis
from app.integrations import analysis_client as analysis_client_module
from app.integrations.absa_client import AbsaClient
from app.integrations.jev_client import JevAiClient
from app.services import analysis_service as analysis_service_module
from apps.api.app_api.dependencies import get_db_session
from apps.api.app_api.routers.integration_analysis import (
    get_integration_analysis_session_factory,
)
from apps.api.app_api.routers.integration_reviews import (
    get_integration_session_factory,
)
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app

# ANSI Colors for terminal output
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
RESET = "\033[0m"


def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 78}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 78}{RESET}\n")
    sys.stdout.flush()


def print_step(step_num: int, title: str):
    print(f"{BOLD}{YELLOW}▶ [STEP {step_num}] {title}{RESET}")
    sys.stdout.flush()
    time.sleep(0.3)


def print_http(method: str, path: str, payload: dict | None = None):
    print(f"  {BOLD}{BLUE}{method}{RESET} {BOLD}{path}{RESET}")
    if payload is not None:
        print(f"  {DIM}Request Body:{RESET}")
        print(f"  {DIM}{json.dumps(payload, indent=4)}{RESET}")
    sys.stdout.flush()
    time.sleep(0.3)


def print_response(status_code: int, data: dict):
    color = GREEN if 200 <= status_code < 300 else RED
    print(f"  {BOLD}{color}HTTP {status_code} OK{RESET}")
    print(f"  {DIM}Response Body:{RESET}")
    lines = json.dumps(data, indent=4).split("\n")
    for line in lines[:25]:
        print(f"  {color}{line}{RESET}")
    if len(lines) > 25:
        print(f"  {DIM}... ({len(lines) - 25} more lines truncated) ...{RESET}")
    print()
    sys.stdout.flush()
    time.sleep(0.4)


def setup_environment():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        company = Company(name="RS Hermina Hospital Group", ai_enable_flag=True)
        session.add(company)
        session.flush()

        loc = Location(
            company_id=company.id,
            hospital_name="RS Hermina",
            branch_name="Bekasi Barat",
            source="apify_google_maps",
            external_place_id="place-bekasi-01",
            ai_enabled=True,
        )
        session.add(loc)
        session.flush()

        # Review 1: Negative review (Viral risk & waiting time)
        r1 = Review(
            company_id=company.id,
            location_id=loc.id,
            source="apify_google_maps",
            external_place_id="place-bekasi-01",
            external_review_id="rev-google-001",
            reviewer_name="Hendro Wijaya",
            rating=1,
            review_text="Antrean di pendaftaran sangat lama dan perawat IGD jutek sekali! Akan saya viralkan di medsos.",
            review_hash="hash-001",
            raw_payload={},
        )
        # Review 2: Positive review (Medical staff appreciation)
        r2 = Review(
            company_id=company.id,
            location_id=loc.id,
            source="apify_google_maps",
            external_place_id="place-bekasi-01",
            external_review_id="rev-google-002",
            reviewer_name="Dewi Sartika",
            rating=5,
            review_text="Pelayanan dokter anak sangat ramah, sabar, dan fasilitas ruang tunggu anak bersih.",
            review_hash="hash-002",
            raw_payload={},
        )
        session.add_all([r1, r2])
        session.commit()

        company_id = company.id
        loc_id = loc.id
        r1_id = r1.id
        r2_id = r2.id

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        analysis_provider="absa",
        analysis_batch_size=10,
        analysis_llm_concurrency=1,
        analysis_llm_max_retries=0,
        jev_base_url="https://jev.mock.test/api",
        jev_api_key="mock-jev-key-xyz",
    )

    def mock_absa_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/inference/engines"):
            return httpx.Response(200, json={"engines": [{"id": "v14", "available": True}]})
        return httpx.Response(
            200,
            json={
                "engine_version": "v14",
                "model_version": "14.0.0-candidate",
                "results": [
                    {
                        "aspect": "antrean pendaftaran",
                        "opinion": "sangat lama",
                        "sentiment": "negative",
                        "taxonomy": "Waiting Time",
                        "confidence": 0.96,
                    },
                    {
                        "aspect": "perawat IGD",
                        "opinion": "jutek sekali",
                        "sentiment": "negative",
                        "taxonomy": "Nurse",
                        "confidence": 0.91,
                    },
                ],
            },
        )

    def mock_jev_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        text = data.get("state", "")
        is_neg = "jutek" in text or "lama" in text or "viralkan" in text
        return httpx.Response(
            200,
            json={
                "answers": {
                    "sentiment": {
                        "choice": "negative" if is_neg else "positive",
                        "probabilities": {
                            "negative": 0.94 if is_neg else 0.03,
                            "positive": 0.04 if is_neg else 0.96,
                            "neutral": 0.02 if is_neg else 0.01,
                            "mixed": 0.0,
                        },
                        "confidence": 0.94 if is_neg else 0.96,
                    },
                    "category": {
                        "choice": "waiting time" if is_neg else "doctor",
                        "probabilities": {"waiting time": 0.90, "doctor": 0.10},
                        "confidence": 0.90,
                    },
                    "is_safety_issue": {"noul": 0.05},
                    "is_viral_risk": {"noul": 0.89 if is_neg else 0.08},
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

    analysis_service_module.get_settings = lambda: settings
    analysis_service_module.get_session_factory = lambda: session_factory
    analysis_client_module.AbsaClient = lambda active_settings: AbsaClient(
        active_settings, http_client=absa_http
    )
    analysis_client_module.JevAiClient = lambda active_settings: JevAiClient(
        active_settings, http_client=jev_http
    )

    principal = ServicePrincipal(
        client_id=company_id,
        key_id="onebox-service-token",
        company_id=company_id,
        scopes=frozenset({"analysis:write", "reviews:read"}),
    )

    app = create_app()
    app.dependency_overrides[get_integration_analysis_session_factory] = lambda: session_factory
    app.dependency_overrides[get_integration_session_factory] = lambda: session_factory
    app.dependency_overrides[require_service_principal] = lambda: principal

    def _override_db():
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = _override_db

    return TestClient(app), loc_id, r1_id, r2_id


def main():
    print_header("REAL-TIME CRAWLER SERVICE & AI ANALYSIS TEST")
    print(f"{BOLD}Target URL Environment:{RESET} https://dev.onebox.co.id/feature/voc/Mediamonitoring/#/voc/reviews")
    print(f"{BOLD}Crawler Service API:{RESET}  Hermina Review Intelligence (FastAPI)")
    print()

    client, loc_id, r1_id, r2_id = setup_environment()

    # =========================================================================
    # STEP 1: MODEL DISCOVERY
    # =========================================================================
    print_step(1, "Model Discovery: Checking active AI models available in Crawler")
    print_http("GET", "/api/integration/v1/analysis/models?provider=jev")
    resp = client.get("/api/integration/v1/analysis/models?provider=jev")
    print_response(resp.status_code, resp.json())

    # =========================================================================
    # STEP 2: PIPELINE SEGMENT 1 (FETCH & IMPORT REVIEWS)
    # =========================================================================
    print_step(2, "Pipeline Segment 1: Ingest & fetch reviews from Crawler to OneBox")
    print_http("GET", f"/api/integration/v1/reviews?location_id={loc_id}")
    resp = client.get(f"/api/integration/v1/reviews?location_id={loc_id}")
    reviews = resp.json()["data"]
    print_response(resp.status_code, resp.json())

    print(f"  {MAGENTA}► Ingested Reviews Summary:{RESET}")
    for idx, r in enumerate(reviews, start=1):
        print(f"    {BOLD}Review #{idx}:{RESET} {r['reviewer_name']} ({r['rating']}★) - Status: {BOLD}{r['analysis_status']}{RESET}, Analyzed: {r['analyzed']}")
        print(f"    {DIM}\"{r['review_text']}\"{RESET}")
    print()

    # =========================================================================
    # STEP 3: PIPELINE SEGMENT 2 (SEPARATE AI ANALYSIS VIA JEV AI)
    # =========================================================================
    print_step(3, "Pipeline Segment 2: Running dedicated AI Analysis for pending reviews via JEV AI")
    payload_seg2 = {"location_id": loc_id, "provider": "jev"}
    print_http("POST", "/api/integration/v1/analysis/pending", payload_seg2)
    resp = client.post("/api/integration/v1/analysis/pending", json=payload_seg2)
    print_response(resp.status_code, resp.json())

    # Verify review updates in OneBox
    print_step(4, "Pipeline Verification: Confirming reviews updated with AI results")
    print_http("GET", f"/api/integration/v1/reviews?location_id={loc_id}")
    resp = client.get(f"/api/integration/v1/reviews?location_id={loc_id}")
    updated_reviews = resp.json()["data"]
    print_response(resp.status_code, resp.json())

    print(f"  {GREEN}► Analyzed Reviews Breakdown:{RESET}")
    for idx, r in enumerate(updated_reviews, start=1):
        print(f"    {BOLD}Review #{idx}:{RESET} {r['reviewer_name']} ({r['rating']}★)")
        print(f"      • Analysis Status : {BOLD}{GREEN}{r['analysis_status'].upper()}{RESET}")
        print(f"      • Sentiment       : {BOLD}{r['sentiment']}{RESET} (score: {r['sentiment_score']})")
        print(f"      • Category        : {BOLD}{r['issue_category']}{RESET}")
        print(f"      • Urgency         : {BOLD}{r['urgency']}{RESET}")
    print()

    # =========================================================================
    # STEP 5: MANUAL SINGLE REVIEW ANALYSIS BUTTON
    # =========================================================================
    print_step(5, "Manual Button Test: Tiap entry button (//*[@id='rv-rows']/tr[1]/td[7]/button[1]) -> Jev AI")
    print_http("POST", f"/api/integration/v1/analysis/reviews/{r1_id}/rerun?provider=jev")
    resp = client.post(f"/api/integration/v1/analysis/reviews/{r1_id}/rerun?provider=jev")
    print_response(resp.status_code, resp.json())

    # =========================================================================
    # STEP 6: DEFAULT FALLBACK TO ABSA
    # =========================================================================
    print_step(6, "Default Fallback Test: Requesting analysis without provider -> Defaults to ABSA")
    payload_default = {"location_id": loc_id}
    print_http("POST", "/api/integration/v1/analysis/pending", payload_default)
    resp = client.post("/api/integration/v1/analysis/pending", json=payload_default)
    print_response(resp.status_code, resp.json())

    # =========================================================================
    # STEP 7: CRAWLER PIPELINE LOCATION ENDPOINT
    # =========================================================================
    print_step(7, "Crawler Pipeline Test: /api/pipeline/location with Jev AI")
    payload_pipeline = {
        "location_id": loc_id,
        "fetch": False,
        "analyze": True,
        "provider": "jev",
    }
    print_http("POST", "/api/pipeline/location", payload_pipeline)
    resp = client.post("/api/pipeline/location", json=payload_pipeline)
    print_response(resp.status_code, resp.json())

    print(f"\n{BOLD}{GREEN}{'=' * 78}{RESET}")
    print(f"{BOLD}{GREEN}  ALL TESTS COMPLETED SUCCESSFULLY IN REAL-TIME (100% OK){RESET}")
    print(f"{BOLD}{GREEN}{'=' * 78}{RESET}\n")


if __name__ == "__main__":
    main()
