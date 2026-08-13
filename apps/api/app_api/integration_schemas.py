"""Frozen v1 contract consumed by OneBox.

Deliberately isolated from ``apps.api.app_api.schemas``: the FE schema is free to
gain, drop, or rename fields, and none of that may leak into this contract. The
enum members below are duplicated from ``app.services.analysis_service`` rather
than imported so that widening the analyzer's vocabulary cannot silently widen
the published contract; ``test_integration_api_contract`` fails when the two
drift apart, forcing that decision to be made explicitly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

Sentiment = Literal["positive", "neutral", "negative", "mixed", "unknown"]
Urgency = Literal["low", "medium", "high", "critical", "unknown"]
IssueCategory = Literal[
    "doctor_service",
    "nurse_service",
    "administration",
    "waiting_time",
    "cleanliness",
    "facility",
    "parking",
    "billing",
    "pharmacy",
    "emergency_room",
    "inpatient",
    "customer_service",
    "booking_system",
    "staff_communication",
    "security",
    "food",
    "general_praise",
    "other",
]
AnalysisStatus = Literal["pending", "completed", "failed", "incomplete"]

API_VERSION = "v1"
DEFAULT_LIMIT = 100
MIN_LIMIT = 1
MAX_LIMIT = 200


def to_utc_z(value: datetime) -> str:
    """Render a datetime as UTC ISO 8601 with a ``Z`` suffix.

    ``datetime.isoformat()`` emits ``+00:00``, which the contract does not allow.
    Naive values are read as UTC: SQLite drops tzinfo on round-trip, so a naive
    value here means "already stored as UTC", not "local time".
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntegrationReviewItem(_Base):
    id: int
    location_id: int
    location: str
    source: str
    external_place_id: str | None = None
    external_review_id: str | None = None
    review_hash: str
    reviewer_name: str | None = None
    reviewer_profile_url: str | None = None
    rating: int | None = None
    review_text: str
    review_time: datetime | None = None
    owner_response_text: str | None = None
    owner_response_time: datetime | None = None
    updated_at: datetime
    sync_updated_at: datetime

    analysis_status: AnalysisStatus
    analyzed: bool
    # Null for every one of these when analyzed is false. keywords and the two
    # flags stay non-null with empty/false defaults so consumers never have to
    # null-check a collection; see api-contract-v1.md.
    sentiment: Sentiment | None = None
    sentiment_score: float | None = None
    issue_category: IssueCategory | None = None
    urgency: Urgency | None = None
    summary: str | None = None
    recommended_action: str | None = None
    keywords: list[str] = []
    is_potential_viral: bool = False
    is_patient_safety_issue: bool = False

    @field_serializer(
        "review_time", "owner_response_time", "updated_at", "sync_updated_at"
    )
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return to_utc_z(value) if value is not None else None


class IntegrationPage(_Base):
    limit: int
    has_more: bool
    # Exactly one of these is set. next_cursor means "more rows in this snapshot";
    # checkpoint_cursor means "snapshot drained, resume the next cycle from here".
    # The consumer must only persist checkpoint_cursor after the whole cycle has
    # been ingested — persisting it early is how rows get skipped.
    next_cursor: str | None = None
    checkpoint_cursor: str | None = None
    snapshot_at: datetime

    @field_serializer("snapshot_at")
    def _serialize_snapshot_at(self, value: datetime) -> str:
        return to_utc_z(value)


class IntegrationMeta(_Base):
    api_version: Literal["v1"] = API_VERSION
    request_id: str


class IntegrationReviewListResponse(_Base):
    data: list[IntegrationReviewItem]
    page: IntegrationPage
    meta: IntegrationMeta


class IntegrationErrorBody(_Base):
    code: str
    message: str
    request_id: str


class IntegrationErrorResponse(_Base):
    error: IntegrationErrorBody

class ServiceIdentityResponse(_Base):
    """Identity returned by whoami; safe for OneBox preflight validation."""

    company_id: int
    company_name: str
    scopes: list[str]
