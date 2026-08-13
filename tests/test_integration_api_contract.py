"""Contract tests for the OneBox v1 integration endpoint (VOC-CS-01).

These tests exist to make a breaking change loud. OneBox parses this response, so
a dropped field, a widened enum, a "+00:00" instead of a "Z", or a leaked
raw_payload is a production incident on their side, not a cosmetic diff here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Company, Location, Review, ReviewAnalysis, User
from app.services.analysis_service import (
    ANALYSIS_STATUSES,
    ALLOWED_CATEGORIES,
    ALLOWED_SENTIMENTS,
    ALLOWED_URGENCIES,
)
from apps.api.app_api.dependencies import get_current_user
from apps.api.app_api.integration_schemas import (
    AnalysisStatus,
    IntegrationReviewListResponse,
    IssueCategory,
    Sentiment,
    Urgency,
)
from apps.api.app_api.routers.integration_reviews import (
    ServicePrincipal,
    get_integration_session_factory,
    require_service_principal,
)
from apps.api.main import create_app

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "voc_reviews_v1.json"

BASE_TIME = datetime(2026, 7, 10, 2, 0, 0, tzinfo=timezone.utc)

FORBIDDEN_FIELDS = {"raw_payload", "raw_response", "company_id"}

# Frozen on purpose: the assertion is that this exact set ships, so removing a
# field or sneaking one in both fail.
EXPECTED_ITEM_FIELDS = {
    "id",
    "location_id",
    "location",
    "source",
    "external_place_id",
    "external_review_id",
    "review_hash",
    "reviewer_name",
    "reviewer_profile_url",
    "rating",
    "review_text",
    "review_time",
    "owner_response_text",
    "owner_response_time",
    "updated_at",
    "sync_updated_at",
    "analysis_status",
    "analyzed",
    "sentiment",
    "sentiment_score",
    "issue_category",
    "urgency",
    "summary",
    "recommended_action",
    "keywords",
    "is_potential_viral",
    "is_patient_safety_issue",
}

ANALYSIS_ONLY_FIELDS = {
    "sentiment",
    "sentiment_score",
    "issue_category",
    "urgency",
    "summary",
    "recommended_action",
}


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
def seeded(session_factory):
    """One tenant with three reviews, plus a second tenant used to prove isolation."""
    with session_factory() as session:
        tenant = Company(name="Hermina", ai_enable_flag=True, total_enable_review=100)
        other = Company(name="Rival", ai_enable_flag=True, total_enable_review=100)
        session.add_all([tenant, other])
        session.commit()

        depok = Location(
            company_id=tenant.id,
            hospital_name="Hermina",
            branch_name="Cabang Depok",
            source="selenium_google_maps",
            external_place_id="place-depok-1",
        )
        bekasi = Location(
            company_id=tenant.id,
            hospital_name="Hermina",
            branch_name="Cabang Bekasi",
            source="selenium_google_maps",
            external_place_id="place-bekasi-1",
        )
        foreign = Location(
            company_id=other.id,
            hospital_name="Rival",
            branch_name="Rival Branch",
            source="selenium_google_maps",
            external_place_id="place-rival-1",
        )
        session.add_all([depok, bekasi, foreign])
        session.commit()

        positive = Review(
            company_id=tenant.id,
            location_id=depok.id,
            source="selenium_google_maps",
            external_place_id="place-depok-1",
            external_review_id="review-depok-1",
            reviewer_name="Customer A",
            rating=5,
            review_text="Dokternya ramah.",
            review_time=BASE_TIME,
            review_hash="hash-positive",
            raw_payload={"secret": "must-not-leak"},
            created_at=BASE_TIME,
            updated_at=BASE_TIME + timedelta(hours=1),
            # Set explicitly to the value the CS-02 backfill produces
            # (max of updated_at, created_at, latest analysis created_at).
            sync_updated_at=BASE_TIME + timedelta(hours=2),
            analysis_status="completed",
        )
        negative = Review(
            company_id=tenant.id,
            location_id=depok.id,
            source="selenium_google_maps",
            external_place_id="place-depok-1",
            external_review_id="review-depok-2",
            reviewer_name="Customer B",
            rating=1,
            review_text="Pasien IGD menunggu berjam-jam.",
            review_time=BASE_TIME + timedelta(days=2),
            review_hash="hash-negative",
            raw_payload={"secret": "must-not-leak"},
            created_at=BASE_TIME + timedelta(days=2),
            updated_at=BASE_TIME + timedelta(days=2, hours=1),
            sync_updated_at=BASE_TIME + timedelta(days=2, hours=2),
            analysis_status="completed",
        )
        unanalyzed = Review(
            company_id=tenant.id,
            location_id=bekasi.id,
            source="selenium_google_maps",
            external_place_id="place-bekasi-1",
            rating=3,
            review_text="Parkirannya sempit.",
            review_time=BASE_TIME + timedelta(days=3),
            review_hash="hash-unanalyzed",
            raw_payload={"secret": "must-not-leak"},
            created_at=BASE_TIME + timedelta(days=3),
            updated_at=BASE_TIME + timedelta(days=3),
            # No analysis, so the watermark is just the review's own updated_at.
            sync_updated_at=BASE_TIME + timedelta(days=3),
        )
        session.add_all([positive, negative, unanalyzed])
        session.commit()

        session.add_all(
            [
                ReviewAnalysis(
                    review_id=positive.id,
                    sentiment="positive",
                    sentiment_score=0.9312,
                    issue_category="doctor_service",
                    urgency="low",
                    summary="Pujian untuk dokter.",
                    recommended_action="Teruskan ke tim dokter.",
                    keywords=["dokter", "ramah"],
                    is_potential_viral=False,
                    is_patient_safety_issue=False,
                    raw_response={"secret": "must-not-leak"},
                    created_at=BASE_TIME + timedelta(hours=2),
                ),
                ReviewAnalysis(
                    review_id=negative.id,
                    sentiment="negative",
                    sentiment_score=0.9714,
                    issue_category="emergency_room",
                    urgency="critical",
                    summary="Keterlambatan penanganan IGD.",
                    recommended_action="Eskalasi ke kepala IGD.",
                    keywords=["igd", "menunggu"],
                    is_potential_viral=True,
                    is_patient_safety_issue=True,
                    raw_response={"secret": "must-not-leak"},
                    created_at=BASE_TIME + timedelta(days=2, hours=2),
                ),
            ]
        )
        session.commit()

        return {
            "company_id": tenant.id,
            "other_company_id": other.id,
            "depok_id": depok.id,
            "bekasi_id": bekasi.id,
            "foreign_location_id": foreign.id,
        }


@pytest.fixture()
def app(session_factory, seeded):
    application = create_app()
    application.dependency_overrides[get_integration_session_factory] = (
        lambda: session_factory
    )
    application.dependency_overrides[require_service_principal] = lambda: ServicePrincipal(
        client_id=1,
        key_id="voc_test_key",
        company_id=seeded["company_id"],
        scopes=frozenset({"reviews:read"}),
    )
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


def _get(client, **params):
    response = client.get("/api/integration/v1/reviews", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Contract shape
# --------------------------------------------------------------------------- #


def test_endpoint_is_published_in_openapi(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/integration/v1/reviews" in schema["paths"]

    operation = schema["paths"]["/api/integration/v1/reviews"]["get"]
    assert [param["name"] for param in operation["parameters"]] == [
        "limit",
        "cursor",
        "updated_since",
        "location_id",
        "X-Request-ID",
    ]
    # 422 is never returned here (validation_error_handler remaps it to 400), so it
    # must not be advertised either.
    assert "422" not in operation["responses"]
    assert {"200", "400", "401", "403", "404"} <= set(operation["responses"])


def test_openapi_still_advertises_422_for_fe_routes(client):
    """The 422 suppression is scoped to the integration prefix."""
    schema = client.get("/api/openapi.json").json()
    assert "422" in schema["paths"]["/api/reviews"]["get"]["responses"]


def test_success_response_validates_against_contract(client):
    payload = _get(client, limit=100)
    IntegrationReviewListResponse.model_validate(payload)

    assert len(payload["data"]) == 3
    assert payload["page"]["limit"] == 100
    assert payload["page"]["has_more"] is False
    # Snapshot drained in one page: no next_cursor, but a checkpoint to resume from.
    assert payload["page"]["next_cursor"] is None
    assert payload["page"]["checkpoint_cursor"]
    assert payload["meta"]["api_version"] == "v1"
    assert payload["meta"]["request_id"]


def test_item_exposes_exactly_the_contract_fields(client):
    payload = _get(client, limit=100)
    for item in payload["data"]:
        assert set(item) == EXPECTED_ITEM_FIELDS


def test_request_id_echoes_the_caller_header(client):
    response = client.get(
        "/api/integration/v1/reviews",
        headers={"X-Request-ID": "voc-contract-smoke"},
    )
    assert response.json()["meta"]["request_id"] == "voc-contract-smoke"


# --------------------------------------------------------------------------- #
# Leakage
# --------------------------------------------------------------------------- #


def test_no_raw_or_tenant_fields_anywhere_in_the_response(client):
    payload = _get(client, limit=100)
    # Substring check over the serialised body, so a leak nested inside any future
    # sub-object is caught too, not just a top-level key.
    body = json.dumps(payload)
    for field in FORBIDDEN_FIELDS:
        assert field not in body
    assert "must-not-leak" not in body


# --------------------------------------------------------------------------- #
# Analysis nullability
# --------------------------------------------------------------------------- #


def test_unanalyzed_review_nulls_every_analysis_field(client):
    payload = _get(client, limit=100)
    unanalyzed = [item for item in payload["data"] if not item["analyzed"]]
    assert len(unanalyzed) == 1

    item = unanalyzed[0]
    for field in ANALYSIS_ONLY_FIELDS:
        assert item[field] is None, field
    # Collections stay non-null so consumers never null-check them.
    assert item["keywords"] == []
    assert item["is_potential_viral"] is False
    assert item["is_patient_safety_issue"] is False


def test_analyzed_reviews_carry_their_analysis(client):
    payload = _get(client, limit=100)
    by_hash = {item["review_hash"]: item for item in payload["data"]}

    critical = by_hash["hash-negative"]
    assert critical["analyzed"] is True
    assert critical["analysis_status"] == "completed"
    assert critical["sentiment"] == "negative"
    assert critical["urgency"] == "critical"
    assert critical["issue_category"] == "emergency_room"
    assert critical["is_patient_safety_issue"] is True
    assert critical["summary"]
    assert critical["recommended_action"]

    praise = by_hash["hash-positive"]
    assert praise["sentiment"] == "positive"
    assert praise["urgency"] == "low"


# --------------------------------------------------------------------------- #
# Enums and timestamps
# --------------------------------------------------------------------------- #


def test_contract_enums_match_analysis_service():
    """Widening the analyzer must not silently widen the published contract."""
    assert set(get_args(Sentiment)) == ALLOWED_SENTIMENTS
    assert set(get_args(Urgency)) == ALLOWED_URGENCIES
    assert set(get_args(IssueCategory)) == ALLOWED_CATEGORIES
    assert set(get_args(AnalysisStatus)) == ANALYSIS_STATUSES


def test_every_timestamp_is_utc_with_a_z_suffix(client):
    payload = _get(client, limit=100)
    stamps = [payload["page"]["snapshot_at"]]
    for item in payload["data"]:
        stamps.extend(
            item[field]
            for field in ("review_time", "owner_response_time", "updated_at", "sync_updated_at")
        )

    for stamp in stamps:
        if stamp is None:
            continue
        assert stamp.endswith("Z"), stamp
        assert "+00:00" not in stamp
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None


def test_sync_updated_at_is_exposed_and_differs_from_updated_at(client, seeded):
    """The watermark is its own column, not an alias of updated_at.

    A consumer paging on updated_at would miss a review whose analysis landed
    later, which is exactly the drift the two timestamps below encode.
    """
    payload = _get(client, limit=100)
    by_hash = {item["review_hash"]: item for item in payload["data"]}

    # Analysis landed after the review row was last touched, so it moved the
    # watermark past updated_at.
    positive = by_hash["hash-positive"]
    assert positive["updated_at"] == "2026-07-10T03:00:00Z"
    assert positive["sync_updated_at"] == "2026-07-10T04:00:00Z"

    assert by_hash["hash-negative"]["sync_updated_at"] == "2026-07-12T04:00:00Z"
    # No analysis: watermark equals the review's own updated_at.
    unanalyzed = by_hash["hash-unanalyzed"]
    assert unanalyzed["sync_updated_at"] == unanalyzed["updated_at"]


# --------------------------------------------------------------------------- #
# Golden fixture
# --------------------------------------------------------------------------- #


def test_golden_fixture_roundtrips_without_drift():
    raw = json.loads(FIXTURE_PATH.read_text())
    dumped = IntegrationReviewListResponse.model_validate(raw).model_dump(mode="json")
    assert dumped == raw


def test_golden_fixture_covers_the_three_required_cases():
    raw = json.loads(FIXTURE_PATH.read_text())
    items = raw["data"]
    assert len(items) == 3

    analyzed = [item for item in items if item["analyzed"]]
    unanalyzed = [item for item in items if not item["analyzed"]]
    assert len(unanalyzed) == 1
    assert {item["sentiment"] for item in analyzed} == {"positive", "negative"}
    assert any(item["urgency"] == "critical" for item in analyzed)

    body = json.dumps(raw)
    for field in FORBIDDEN_FIELDS:
        assert field not in body


# --------------------------------------------------------------------------- #
# Parameters, pagination, tenancy
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("limit", [0, 201])
def test_limit_outside_the_allowed_range_is_400(client, limit):
    response = client.get("/api/integration/v1/reviews", params={"limit": limit})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_PARAMETER"
    assert error["request_id"]


def test_malformed_parameter_type_is_400_not_422(client):
    response = client.get("/api/integration/v1/reviews", params={"limit": "abc"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_updated_since_without_timezone_is_rejected(client):
    response = client.get(
        "/api/integration/v1/reviews", params={"updated_since": "2026-07-01T00:00:00"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_updated_since_filters_on_the_watermark(client):
    payload = _get(client, updated_since="2026-07-12T00:00:00Z")
    hashes = {item["review_hash"] for item in payload["data"]}
    assert hashes == {"hash-negative", "hash-unanalyzed"}


def test_cursor_cannot_be_combined_with_updated_since(client):
    first = _get(client, limit=1)
    response = client.get(
        "/api/integration/v1/reviews",
        params={
            "cursor": first["page"]["next_cursor"],
            "updated_since": "2026-07-01T00:00:00Z",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR_CONTEXT"


def test_tampered_cursor_is_rejected(client):
    response = client.get(
        "/api/integration/v1/reviews", params={"cursor": "not-a-real-cursor"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_cursor_walks_every_review_exactly_once(client):
    seen: list[int] = []
    cursor = None
    for _ in range(5):  # bounded so a broken cursor cannot spin forever
        params = {"limit": 1}
        if cursor:
            params["cursor"] = cursor
        payload = _get(client, **params)
        seen.extend(item["id"] for item in payload["data"])
        cursor = payload["page"]["next_cursor"]
        if not payload["page"]["has_more"]:
            break

    assert cursor is None
    assert len(seen) == 3
    assert len(set(seen)) == 3


def test_location_id_filters_within_the_tenant(client, seeded):
    payload = _get(client, location_id=seeded["bekasi_id"])
    assert [item["review_hash"] for item in payload["data"]] == ["hash-unanalyzed"]


def test_another_tenants_location_is_404(client, seeded):
    response = client.get(
        "/api/integration/v1/reviews",
        params={"location_id": seeded["foreign_location_id"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"


# --------------------------------------------------------------------------- #
# Auth placeholder + FE regression
# --------------------------------------------------------------------------- #


def test_endpoint_requires_service_token():
    """No override: the route must refuse, never fall open."""
    unguarded = TestClient(create_app())
    response = unguarded.get("/api/integration/v1/reviews")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SERVICE_TOKEN"


def test_missing_scope_is_403(session_factory, seeded):
    application = create_app()
    application.dependency_overrides[get_integration_session_factory] = (
        lambda: session_factory
    )
    application.dependency_overrides[require_service_principal] = lambda: ServicePrincipal(
        client_id=1,
        key_id="voc_test_key",
        company_id=seeded["company_id"],
        scopes=frozenset(),  # no reviews:read
    )
    response = TestClient(application).get("/api/integration/v1/reviews")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_existing_fe_reviews_route_is_untouched():
    schema = TestClient(create_app()).get("/api/openapi.json").json()
    assert "/api/reviews" in schema["paths"]
    assert "/api/reviews/{review_id}" in schema["paths"]
    # The FE reads items/total/page/page_size/total_pages; the integration work is
    # additive and must not have reshaped that envelope.
    fe_response = schema["paths"]["/api/reviews"]["get"]["responses"]["200"]
    fe_schema_ref = fe_response["content"]["application/json"]["schema"]["$ref"]
    assert fe_schema_ref.endswith("ReviewListResponse")
    fe_fields = schema["components"]["schemas"]["ReviewListResponse"]["properties"]
    assert set(fe_fields) == {"items", "total", "page", "page_size", "total_pages"}


def test_fe_validation_still_returns_422(seeded):
    """The 400 remap is scoped to /api/integration/; FE error behaviour must not move."""
    application = create_app()
    # Stand in for the JWT so the request reaches parameter validation rather than
    # stopping at the 401. The bad `page` is rejected before the route body runs,
    # so no database access happens here.
    application.dependency_overrides[get_current_user] = lambda: User(
        id=1, company_id=seeded["company_id"], email="fe@test.local", is_active=True
    )
    response = TestClient(application).get("/api/reviews", params={"page": "not-an-int"})
    assert response.status_code == 422
