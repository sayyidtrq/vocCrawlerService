from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.db.models import Competitor, Location


@dataclass(frozen=True)
class CrawlTarget:
    kind: Literal["location", "competitor"]
    id: int
    branch_name: str
    hospital_name: str
    external_place_id: str | None
    google_maps_url: str | None
    google_reviews_url: str | None
    target_review_count: int
    source: str

    @classmethod
    def from_location(cls, location: Location) -> "CrawlTarget":
        return cls(
            kind="location",
            id=location.id,
            branch_name=location.branch_name,
            hospital_name=location.hospital_name,
            external_place_id=location.external_place_id,
            google_maps_url=location.google_maps_url,
            google_reviews_url=location.google_reviews_url,
            target_review_count=location.target_review_count,
            source=location.source,
        )

    @classmethod
    def from_competitor(cls, competitor: Competitor) -> "CrawlTarget":
        return cls(
            kind="competitor",
            id=competitor.id,
            branch_name=competitor.name,
            hospital_name=competitor.name,
            external_place_id=competitor.external_place_id,
            google_maps_url=competitor.google_maps_url,
            google_reviews_url=competitor.google_reviews_url,
            target_review_count=competitor.target_review_count,
            source=competitor.source,
        )
