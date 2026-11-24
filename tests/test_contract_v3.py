from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.models import Company, Location, Review, ReviewAnalysis
from app.services.analysis_service import ALLOWED_CATEGORIES
from app.services.integration_review_service import IntegrationReviewService
from apps.api.app_api.integration_schemas import IntegrationReviewItem
from apps.api.app_api.routers.integration_reviews import get_integration_session_factory
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app

NOW = datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)


def project(analysis):
    review = Review(
        id=7, location_id=3, source="google_maps", review_hash="h", review_text="Takaran kurang.",
        rating=1, analysis_status="completed", updated_at=NOW, sync_updated_at=NOW,
    )
    return IntegrationReviewService._project((review, "Cabang SPBU", analysis, 99))


def analysis(**overrides):
    fields = dict(
        review_id=7, sentiment="negative", sentiment_score=0.9, issue_category="takaran_bbm", urgency="high",
        summary="s", recommended_action="a", keywords=[], is_potential_viral=False, is_safety_issue=False,
    )
    return ReviewAnalysis(**{**fields, **overrides})


def test_a_taxonomy_analysis_passes_its_slug_through_as_v3():
    item = project(
        analysis(
            taxonomy_version="6285c2fa",
            risk_flags={"risiko_viral": False, "risiko_kebakaran": True},
            tags=[
                {"slug": "takaran_bbm", "p": 0.9, "sentiment": "negative"},
                {"slug": "waktu_tunggu", "p": None, "sentiment": "positive"},
            ],
        )
    )

    # not flattened to `other`: it is a slug of the location's own taxonomy
    assert item["issue_category"] == "takaran_bbm"
    assert (item["output_schema_version"], item["taxonomy_version"]) == ("v3", "6285c2fa")

    validated = IntegrationReviewItem(**item)
    assert validated.tags[1].slug == "waktu_tunggu" and validated.tags[1].p is None
    assert (validated.tags[0].sentiment, validated.tags[1].sentiment) == ("negative", "positive")
    assert validated.risk_flags["risiko_kebakaran"] is True


def test_tags_stored_before_per_tag_sentiment_still_serve_with_a_null_sentiment():
    item = project(analysis(taxonomy_version="6285c2fa", risk_flags={}, tags=[{"slug": "takaran_bbm", "p": 0.9}]))
    validated = IntegrationReviewItem(**item)
    assert validated.tags[0].sentiment is None


def test_a_legacy_analysis_is_unchanged_v2_with_null_taxonomy_fields():
    item = project(analysis(issue_category="doctor_service"))

    assert item["issue_category"] == "professional_service"  # historical alias, as before
    assert item["output_schema_version"] == "v2"
    assert (item["taxonomy_version"], item["risk_flags"], item["tags"]) == (None, None, None)
    assert IntegrationReviewItem(**item).issue_category in ALLOWED_CATEGORIES


def test_an_unanalysed_review_is_v2_with_null_taxonomy_fields():
    item = project(None)

    assert item["output_schema_version"] == "v2" and item["issue_category"] is None
    assert (item["taxonomy_version"], item["risk_flags"], item["tags"]) == (None, None, None)
    IntegrationReviewItem(**item)


def test_the_item_schema_stays_closed():
    item = project(analysis(taxonomy_version="x", risk_flags={}, tags=[{"slug": "a", "p": 0.5, "extra": 1}]))
    with pytest.raises(ValidationError):
        IntegrationReviewItem(**item)  # tags may carry only slug, p and sentiment


def test_the_pull_endpoint_serves_a_taxonomy_analysis(tx_session_factory):
    with tx_session_factory() as session:
        company = Company(name="T", ai_enable_flag=True)
        session.add(company)
        session.flush()
        location = Location(
            company_id=company.id, hospital_name="Org", branch_name="Cabang", source="onebox", external_place_id="p1"
        )
        session.add(location)
        session.flush()
        review = Review(
            company_id=company.id, location_id=location.id, source="google_maps", review_hash="hh",
            review_text="Takaran kurang", rating=1, analysis_status="completed",
        )
        session.add(review)
        session.flush()
        session.add(
            ReviewAnalysis(
                review_id=review.id, sentiment="negative", sentiment_score=0.9, issue_category="takaran_bbm",
                urgency="high", summary="s", recommended_action="a", keywords=[], is_potential_viral=False,
                is_safety_issue=False, taxonomy_version="6285c2fa", risk_flags={"risiko_viral": False},
                tags=[{"slug": "takaran_bbm", "p": 0.9, "sentiment": "negative"}],
            )
        )
        session.commit()
        company_id = company.id

    app = create_app()
    app.dependency_overrides[get_integration_session_factory] = lambda: tx_session_factory
    app.dependency_overrides[require_service_principal] = lambda: ServicePrincipal(
        client_id=1, key_id="k", company_id=company_id, scopes=frozenset({"reviews:read"})
    )
    response = TestClient(app).get("/api/integration/v1/reviews", params={"limit": 10})

    assert response.status_code == 200, response.text
    item = response.json()["data"][0]
    assert item["issue_category"] == "takaran_bbm" and item["output_schema_version"] == "v3"
    assert item["tags"] == [{"slug": "takaran_bbm", "p": 0.9, "sentiment": "negative"}]
