from __future__ import annotations

import re
from datetime import datetime

from app.utils.rating_parser import parse_compact_count, parse_rating

SOURCE_NAME = "selenium_google_maps"


class GoogleMapsReviewParser:
    source_name = SOURCE_NAME

    @staticmethod
    def parse_place_rating(value: str) -> float | None:
        text = str(value or "").replace("\xa0", " ")
        match = re.search(r"(?<!\d)([1-5][.,]\d)(?!\d)", text)
        if not match:
            return None
        try:
            rating = float(match.group(1).replace(",", "."))
        except ValueError:
            return None
        return rating if 1 <= rating <= 5 else None

    @staticmethod
    def parse_place_review_count(value: str) -> int | None:
        text = str(value or "").lower().replace("\xa0", " ")
        match = re.search(
            r"(\d[\d.,]*)\s*(rb|ribu|k|m|jt|juta)?\s*(?:reviews?|ulasan)",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        number_text, suffix = match.groups()
        suffix = suffix or ""
        if suffix:
            try:
                number = float(number_text.replace(",", "."))
            except ValueError:
                return None
            multiplier = 1_000 if suffix in {"rb", "ribu", "k"} else 1_000_000
            return int(number * multiplier)
        digits = re.sub(r"\D", "", number_text)
        return int(digits) if digits else None

    @staticmethod
    def parse_reviewer_total_reviews(value: str) -> int | None:
        match = re.search(
            r"(\d[\d.,]*)\s+(?:reviews?|ulasan)", value, flags=re.IGNORECASE
        )
        if not match:
            return None
        return parse_compact_count(match.group(1), default=0)

    @classmethod
    def parse_review(
        cls, raw: dict, *, source_url: str, scraped_at: datetime
    ) -> dict:
        reviewer_name = raw["reviewer_name"] or "Anonymous"
        reviewer_meta = raw["reviewer_meta"] or ""
        local_guide = (
            "Local Guide"
            if "local guide" in reviewer_meta.lower()
            or "pemandu lokal" in reviewer_meta.lower()
            else None
        )
        total_reviews = cls.parse_reviewer_total_reviews(reviewer_meta)
        raw_payload = {
            "review_id": raw["review_id"],
            "reviewer_name": reviewer_name,
            "reviewer_meta": raw["reviewer_meta"],
            "rating_label": raw["rating_label"],
            "review_text": raw["review_text"],
            "review_relative_time": raw["relative_time"],
            "like_label": raw["like_label"],
            "owner_response_text": raw["owner_text"],
            "owner_response_relative_time": raw["owner_time"],
            "source_url": source_url,
        }
        return {
            "source": SOURCE_NAME,
            "external_review_id": raw["review_id"],
            "reviewer_name": reviewer_name,
            "reviewer_profile_url": raw["profile_url"],
            "reviewer_photo_url": raw["photo_url"],
            "reviewer_local_guide_level": local_guide,
            "reviewer_total_reviews": total_reviews,
            "rating": parse_rating(raw["rating_label"]),
            "review_text": raw["review_text"],
            "review_relative_time": raw["relative_time"] or None,
            "review_time": None,
            "review_language": "unknown",
            "language": "unknown",
            "like_count": parse_compact_count(raw["like_label"]),
            "owner_response_text": raw["owner_text"] or None,
            "owner_response_time": None,
            "scraped_at": scraped_at.isoformat(),
            "raw_payload": raw_payload,
        }

    @staticmethod
    def review_identity(review: dict) -> str:
        external_review_id = " ".join(
            str(review.get("external_review_id") or "").split()
        )
        if external_review_id:
            return f"external:{external_review_id}"
        parts = [
            review.get("reviewer_profile_url"),
            review.get("reviewer_name"),
            review.get("rating"),
            review.get("review_text"),
        ]
        return "fallback:" + "|".join(
            " ".join(str(part or "").split()) for part in parts
        )

    @classmethod
    def parse_place_snapshot(cls, source_text: str, *, snapshot_at: datetime) -> dict:
        place_rating = cls.parse_place_rating(source_text)
        place_review_count = cls.parse_place_review_count(source_text)
        snapshot = {
            "source": "google_maps",
            "place_rating": place_rating,
            "place_review_count": place_review_count,
            "snapshot_at": snapshot_at.isoformat(),
        }
        return {
            "place_rating": place_rating,
            "place_review_count": place_review_count,
            "rating_snapshot_at": snapshot["snapshot_at"],
            "rating_snapshot": snapshot,
        }
