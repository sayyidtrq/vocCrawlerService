from __future__ import annotations


class ApifyReviewParser:
    @staticmethod
    def parse_review(item: dict) -> dict:
        language = item.get("content_language")
        return {
            "source": "apify_google_maps",
            "external_place_id": item.get("place_id"),
            "external_review_id": item.get("review_id"),
            "reviewer_name": item.get("reviewer_name"),
            "reviewer_profile_url": item.get("reviewer_url"),
            "reviewer_photo_url": item.get("reviewer_photo_url")
            or item.get("reviewer_photo"),
            "reviewer_local_guide_level": "Local Guide"
            if item.get("is_local_guide") is True
            else None,
            "reviewer_total_reviews": item.get("reviewer_reviews_count"),
            "rating": item.get("rating"),
            "review_text": item.get("content") or "",
            "review_time": item.get("reviewed_at_date"),
            "review_relative_time": item.get("reviewed_at"),
            "review_language": language,
            "language": language,
            "like_count": item.get("likes_count"),
            "owner_response_text": item.get("owner_response"),
            "owner_response_time": item.get("owner_response_at_date"),
            "scraped_at": item.get("scraped_at"),
            "raw_payload": dict(item),
        }
