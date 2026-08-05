from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CrawlTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onebox_location_id: int = Field(gt=0)
    target_review_count: int | None = Field(default=None, ge=1, le=300)

    # Opsional dan backward-compatible: tidak dikirim = ambil semua tanggal.
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
    # Urutan pengambilan di Google Maps. Rentang tanggal hanya bisa dikerjakan
    # pada 'newest'; permintaan lain yang menyertakan rentang akan dipaksa ke
    # sana oleh service, dan alasannya dicatat di metadata job.
    sort_by: Literal[
        "newest", "most_relevant", "highest_rating", "lowest_rating"
    ] = Field(default="newest")

    @model_validator(mode="after")
    def _check_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be later than date_to.")
        return self


class CrawlBatchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str | None = Field(default=None, max_length=50)
    targets: list[CrawlTargetRequest] = Field(min_length=1, max_length=500)


class CrawlJobErrorResponse(BaseModel):
    code: str
    message: str


class CrawlJobResponse(BaseModel):
    target_review_count: int
    job_id: int
    onebox_location_id: int
    status: str
    attempts: int
    max_attempts: int
    result: dict[str, Any]
    error: CrawlJobErrorResponse | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CrawlBatchDataResponse(BaseModel):
    batch_id: str
    status: str
    slot: str | None = None
    job_count: int
    counts: dict[str, int]
    review_counts: dict[str, int]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Cabang yang dikerjakan batch ini. Ikut pada daftar maupun detail, supaya
    # layar Riwayat Fetch OneBox bisa menyebut cabangnya tanpa memanggil detail
    # tiap batch satu per satu. Hanya id-nya: nama cabang milik OneBox.
    targets: list[int] = []
    jobs: list[CrawlJobResponse] | None = None


class CrawlBatchResponse(BaseModel):
    data: CrawlBatchDataResponse
    meta: dict[str, str]


class CrawlBatchListResponse(BaseModel):
    data: list[CrawlBatchDataResponse]
    meta: dict[str, str | int]
