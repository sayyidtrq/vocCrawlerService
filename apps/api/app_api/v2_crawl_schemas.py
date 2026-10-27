from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, model_validator

from apps.api.app_api.integration_schemas import to_utc_z
from apps.api.app_api.v2_common import V2Meta

CrawlMode = Literal["backfill", "delta", "range"]
CrawlStatus = Literal["running", "succeeded", "failed", "aborted", "timed_out", "unknown"]


class CrawlTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    place_id: str = Field(min_length=1, max_length=255)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_id: int = Field(default=0, ge=0, strict=True)
    targets: list[CrawlTarget] = Field(min_length=1, max_length=50)
    mode: CrawlMode = "delta"
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None
    max_reviews: int = Field(default=100, ge=1, le=100000, strict=True)
    sort_by: Literal["newest", "most_relevant", "highest_rating", "lowest_rating"] = "newest"

    @model_validator(mode="after")
    def validate_options(self) -> CrawlRequest:
        places = [target.place_id for target in self.targets]
        if len(set(places)) != len(places):
            raise ValueError("Duplicate place ids are not allowed.")
        if self.mode == "range":
            if self.date_from is None or self.date_to is None or self.date_from > self.date_to:
                raise ValueError("Range mode requires ordered date_from and date_to.")
        elif self.date_to is not None:
            raise ValueError("date_to is only allowed in range mode.")
        return self

class CrawlStartError(BaseModel):
    code: str
    message: str


class CrawlStartRun(BaseModel):
    place_id: str
    crawl_id: str | None = None
    run_id: str | None = None
    status: Literal["started", "failed"]
    error: CrawlStartError | None = None


class CrawlStartData(BaseModel):
    idempotent_replay: bool
    runs: list[CrawlStartRun]


class CrawlStartResponse(BaseModel):
    data: CrawlStartData
    meta: V2Meta


class CrawlReview(BaseModel):
    source: str
    external_place_id: str
    external_review_id: str | None
    review_hash: str
    reviewer_name: str
    reviewer_profile_url: str | None
    review_url: str | None
    review_photo_urls: list[str]
    rating: int | None
    review_text: str
    review_time: datetime | None
    review_time_precision: str | None
    date_approximate: bool
    is_edited: bool
    edited_at: datetime | None
    owner_response_text: str | None
    owner_response_time: datetime | None

    @field_serializer("review_time", "edited_at", "owner_response_time")
    def serialize_date(self, value: datetime | None) -> str | None:
        return to_utc_z(value) if value is not None else None


class CrawlPageData(BaseModel):
    crawl_id: str
    run_id: str
    place_id: str
    status: CrawlStatus
    fetched_so_far: int | None
    reviews: list[CrawlReview]
    next_cursor: str | None
    done: bool


class CrawlPageResponse(BaseModel):
    data: CrawlPageData
    meta: V2Meta
