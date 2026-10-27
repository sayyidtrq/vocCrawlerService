"""Read-only audit backup contracts."""

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer

from apps.api.app_api.integration_schemas import IntegrationMeta, to_utc_z

UtcTimestamp = Annotated[datetime, PlainSerializer(to_utc_z, return_type=str)]
ReviewHash = Annotated[str, Field(min_length=1, max_length=255)]
UNANALYZED_DESCRIPTION = (
    'Reviews with no kind="analysis" row for the same (site_id, review_hash). '
    'Only status analyzed or rating_fallback counts as analysed; a failed analysis and reply suggestions do not.'
)
LAST_CRAWL_DESCRIPTION = "Latest crawl started_at, regardless of status."


class ReviewStats(BaseModel):
    stored_count: int
    newest_review_time: UtcTimestamp | None
    oldest_review_time: UtcTimestamp | None
    first_seen_at: UtcTimestamp | None
    last_seen_at: UtcTimestamp | None
    last_seen_age_seconds: int | None
    unanalyzed_count: int = Field(description=UNANALYZED_DESCRIPTION)


class LastRun(BaseModel):
    run_id: str
    mode: str
    status: str
    started_at: UtcTimestamp
    finished_at: UtcTimestamp | None
    fetched_count: int


class CrawlStats(BaseModel):
    run_count: int
    last_run: LastRun | None
    last_crawl_at: UtcTimestamp | None = Field(description=LAST_CRAWL_DESCRIPTION)
    last_crawl_age_seconds: int | None


class AnalysisStats(BaseModel):
    count: int
    last_analysis_at: UtcTimestamp | None
    by_status: dict[str, int]


class PlaceSummary(BaseModel):
    site_id: int
    place_id: str
    as_of: UtcTimestamp
    reviews: ReviewStats
    crawls: CrawlStats
    analyses: AnalysisStats


class SiteTotals(BaseModel):
    places: int
    reviews: int
    runs: int
    analyses: int = Field(description='All kind="analysis" rows for the site, including hashes without a stored review.')


class PlaceFreshness(BaseModel):
    place_id: str
    stored_count: int
    newest_review_time: UtcTimestamp | None
    last_seen_at: UtcTimestamp | None
    last_crawl_at: UtcTimestamp | None = Field(description=LAST_CRAWL_DESCRIPTION)
    last_crawl_age_seconds: int | None
    unanalyzed_count: int = Field(description=UNANALYZED_DESCRIPTION)


class SiteSummary(BaseModel):
    site_id: int
    as_of: UtcTimestamp
    totals: SiteTotals
    places: list[PlaceFreshness]
    total_places: int
    truncated: bool


class AuditSummaryResponse(BaseModel):
    data: PlaceSummary | SiteSummary
    meta: IntegrationMeta


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_id: int = Field(default=0, ge=0, strict=True)
    place_id: str = Field(min_length=1, max_length=255)
    review_hashes: list[ReviewHash] = Field(max_length=10000, description="Duplicates are collapsed before comparison.")
    since: AwareDatetime | None = None
    limit: int = Field(default=1000, ge=1, le=5000, strict=True)


class ReconcileData(BaseModel):
    site_id: int
    place_id: str
    since: UtcTimestamp | None
    caller_count: int
    backup_count: int
    matched: int
    missing_in_caller: list[str]
    missing_in_caller_count: int
    missing_in_caller_truncated: bool
    missing_in_backup: list[str]
    missing_in_backup_count: int
    missing_in_backup_truncated: bool
    other_place_count: int
    as_of: UtcTimestamp


class ReconcileResponse(BaseModel):
    data: ReconcileData
    meta: IntegrationMeta
