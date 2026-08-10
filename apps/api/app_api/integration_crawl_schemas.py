from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CrawlTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Cabang di-alamati lewat id OneBox; kompetitor tidak bisa, karena
    # kompetitor sengaja tidak dicerminkan ke master Location OneBox (dia bukan
    # cabang kita). Kompetitor karena itu di-alamati lewat Google Place ID.
    kind: Literal["location", "competitor"] = Field(default="location")
    onebox_location_id: int | None = Field(default=None, gt=0)
    external_place_id: str | None = Field(default=None, max_length=255)
    # Hanya untuk jejak audit dari OneBox; tidak dipakai untuk resolusi target.
    onebox_connection_id: int | None = Field(default=None, gt=0)
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
        if self.kind == "location":
            if self.onebox_location_id is None:
                raise ValueError(
                    "onebox_location_id is required when kind is 'location'."
                )
        elif not (self.external_place_id or "").strip():
            raise ValueError(
                "external_place_id is required when kind is 'competitor'."
            )
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
    # Kosong untuk job kompetitor. Tanpa ini serialisasi batch yang memuat
    # kompetitor akan gagal validasi dan berbalik menjadi 500.
    onebox_location_id: int | None = None
    competitor_id: int | None = None
    kind: str = "location"
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
    # location | competitor | mixed. Kompetitor tidak punya onebox_location_id,
    # jadi tanpa penanda ini batch kompetitor tak bisa dibedakan dari batch
    # cabang yang kebetulan tidak punya target.
    kind: str = "location"
    competitors: list[int] = []
    jobs: list[CrawlJobResponse] | None = None


class CrawlBatchResponse(BaseModel):
    data: CrawlBatchDataResponse
    meta: dict[str, str]


class CrawlBatchListResponse(BaseModel):
    data: list[CrawlBatchDataResponse]
    meta: dict[str, str | int]
