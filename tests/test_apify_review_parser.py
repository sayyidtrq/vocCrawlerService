import json
from pathlib import Path

from app.integrations.apify_review_parser import ApifyReviewParser

FIXTURE = Path(__file__).parent / "fixtures" / "apify_google_maps_reviews_sample.json"


def test_real_apify_sample_maps_every_review_column():
    items = json.loads(FIXTURE.read_text())

    assert len(items) == 4
    # Dua tanggal asli (umurnya bukan kelipatan tepat), satu taksiran bulan,
    # satu ulasan yang diedit - tanggalnya tanggal edit, taksiran bulan.
    precisions = ["day", "day", "month", "month"]
    edited = [False, False, False, True]
    for index, item in enumerate(items):
        parsed = ApifyReviewParser.parse_review(item)
        expected = {
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
            "review_time_precision": precisions[index],
            "is_edited": edited[index],
            "edited_at": item.get("reviewed_at_date") if edited[index] else None,
            "review_relative_time": item.get("reviewed_at"),
            "review_language": item.get("content_language"),
            "language": item.get("content_language"),
            "like_count": item.get("likes_count"),
            "owner_response_text": item.get("owner_response"),
            "owner_response_time": item.get("owner_response_at_date"),
            "scraped_at": item.get("scraped_at"),
            "raw_payload": item,
        }
        assert parsed == expected
        assert parsed["raw_payload"]["location"] == item["location"]
        assert "location" not in parsed
