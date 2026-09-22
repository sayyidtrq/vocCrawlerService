from __future__ import annotations

from app.utils.date_parser import (
    is_edited_text,
    parse_datetime,
    relative_time_precision,
)


class ApifyReviewParser:
    @staticmethod
    def parse_review(item: dict) -> dict:
        language = item.get("content_language")
        relative = item.get("reviewed_at")
        # reviewed_at_date kebanyakan taksiran dari teks relatif (spec B17);
        # untuk ulasan yang diedit, tanggal itu adalah tanggal EDIT-nya.
        precision = relative_time_precision(
            relative,
            parse_datetime(item.get("reviewed_at_date")),
            parse_datetime(item.get("scraped_at")),
        )
        edited = is_edited_text(relative)
        return {
            "source": "apify_google_maps",
            "external_place_id": item.get("place_id"),
            "external_review_id": item.get("review_id"),
            "reviewer_name": item.get("reviewer_name"),
            "reviewer_profile_url": item.get("reviewer_url"),
            "review_url": item.get("review_url"),
            "review_photo_urls": item.get("review_photos_urls") or [],
            "reviewer_photo_url": item.get("reviewer_photo_url")
            or item.get("reviewer_photo"),
            "reviewer_local_guide_level": "Local Guide"
            if item.get("is_local_guide") is True
            else None,
            "reviewer_total_reviews": item.get("reviewer_reviews_count"),
            "rating": item.get("rating"),
            "review_text": item.get("content") or "",
            "review_time": item.get("reviewed_at_date"),
            "review_time_precision": precision,
            "is_edited": edited,
            "edited_at": item.get("reviewed_at_date") if edited else None,
            "review_relative_time": relative,
            "review_language": language,
            "language": language,
            "like_count": item.get("likes_count"),
            "owner_response_text": item.get("owner_response"),
            "owner_response_time": item.get("owner_response_at_date"),
            "scraped_at": item.get("scraped_at"),
            "raw_payload": dict(item),
        }
