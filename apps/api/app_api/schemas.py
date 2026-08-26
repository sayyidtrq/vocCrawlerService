"""Response schemas for OpenAPI/Swagger documentation.

These models describe the JSON shape returned by each endpoint so that
`/api/docs`, `/api/redoc`, and `/api/openapi.json` render a complete,
typed contract (useful for the Onebox pull integration).

Design notes:
- All fields are Optional with permissive types. Endpoints build plain
  dicts via `to_jsonable(...)`, so datetimes arrive as ISO strings; we type
  them as `str` to avoid re-parsing. Nested/dynamic parts use `Any`/`list`/`dict`.
- Every field returned by the underlying service is declared here, so
  attaching these as `response_model` does not drop any field from the output.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ErrorDetail(_Base):
    code: str
    message: str


class ErrorResponse(_Base):
    error: ErrorDetail


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
class DatabaseHealth(_Base):
    ok: bool
    message: str | None = None


class HealthResponse(_Base):
    status: str = "ok"
    app: str | None = None
    env: str | None = None
    database: DatabaseHealth | None = None


# --------------------------------------------------------------------------- #
# Locations
# --------------------------------------------------------------------------- #
class LocationResponse(_Base):
    id: int
    hospital_name: str | None = None
    branch_name: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None
    external_place_id: str | None = None
    google_maps_url: str | None = None
    google_reviews_url: str | None = None
    target_review_count: int | None = None
    is_active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LocationListResponse(_Base):
    items: list[LocationResponse]
    total: int


class DeleteResponse(_Base):
    status: str = "success"
    deleted: str | None = None


# --------------------------------------------------------------------------- #
# Reviews (review + embedded AI analysis)
# --------------------------------------------------------------------------- #
class ReviewResponse(_Base):
    id: int
    location_id: int | None = None
    location: str | None = None
    source: str | None = None
    external_place_id: str | None = None
    external_review_id: str | None = None
    reviewer_name: str | None = None
    reviewer_profile_url: str | None = None
    reviewer_photo_url: str | None = None
    reviewer_local_guide_level: str | None = None
    reviewer_total_reviews: int | None = None
    rating: int | None = None
    review_text: str | None = None
    review_time: str | None = None
    review_relative_time: str | None = None
    review_language: str | None = None
    language: str | None = None
    like_count: int | None = None
    owner_response_text: str | None = None
    owner_response_time: str | None = None
    scraped_at: str | None = None
    raw_payload: Any | None = None
    review_hash: str | None = None
    created_at: str | None = None
    # embedded analysis
    analysis_status: str | None = None
    analyzed: bool | None = None
    analysis_id: int | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    issue_category: str | None = None
    urgency: str | None = None
    summary: str | None = None
    recommended_action: str | None = None
    keywords: list[Any] | None = None
    is_potential_viral: bool | None = None
    is_patient_safety_issue: bool | None = None


class ReviewListResponse(_Base):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class DashboardOverviewResponse(_Base):
    total_locations: int | None = None
    total_reviews: int | None = None
    analyzed_reviews: int | None = None
    pending_analysis: int | None = None
    sentiments: dict[str, int] | None = None
    top_issues: list[Any] | None = None
    critical_issues: int | None = None
    latest_fetch: str | None = None


class LocationSummaryResponse(_Base):
    location_id: int | None = None
    location_name: str | None = None
    total_reviews: int | None = None
    average_rating: float | None = None
    sentiments: dict[str, int] | None = None
    top_issues: list[Any] | None = None
    critical_issues: int | None = None
    negative_examples: list[Any] | None = None
    management_focus: list[Any] | None = None


class IssueItem(_Base):
    location: str | None = None
    rating: int | None = None
    review_text: str | None = None
    sentiment: str | None = None
    issue_category: str | None = None
    urgency: str | None = None
    recommended_action: str | None = None


class IssueListResponse(_Base):
    items: list[IssueItem]
    total: int


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
class AnalysisPendingResponse(_Base):
    total: int | None = None
    success: int | None = None
    failed: int | None = None
    skipped_empty: int | None = None
    rating_fallback: int | None = None
    sentiments: dict[str, int] | None = None
    tokens_used: int | None = None
    token_usage: dict[str, int] | None = None
    errors: list[Any] | None = None
    skipped_ai_disabled: int | None = None
    duration_ms: float | None = None
    llm_calls: int | None = None
    llm_retries: int | None = None
    llm_call_ms_total: float | None = None
    quality: dict[str, int] | None = None
    not_attempted: int | None = None
    circuit_breaker_tripped: bool | None = None
    concurrency: int | None = None
    max_in_flight: int | None = None


# --------------------------------------------------------------------------- #
# Fetch logs
# --------------------------------------------------------------------------- #
class FetchLogItem(_Base):
    id: int
    location_id: int | None = None
    location: str | None = None
    source: str | None = None
    status: str | None = None
    total_fetched: int | None = None
    total_inserted: int | None = None
    total_duplicate: int | None = None
    total_failed: int | None = None
    error_message: str | None = None
    metadata: Any | None = None
    started_at: str | None = None
    finished_at: str | None = None


class FetchLogListResponse(_Base):
    items: list[FetchLogItem]
    total: int


class FetchLogLatestResponse(_Base):
    item: FetchLogItem | None = None


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
class ExportResponse(_Base):
    status: str = "success"
    filename: str | None = None
    path: str | None = None


# --------------------------------------------------------------------------- #
# Competitors
# --------------------------------------------------------------------------- #
class CompetitorResponse(_Base):
    id: int
    name: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None
    external_place_id: str | None = None
    google_maps_url: str | None = None
    google_reviews_url: str | None = None
    target_review_count: int | None = None
    is_active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CompetitorListResponse(_Base):
    items: list[CompetitorResponse]
    total: int
