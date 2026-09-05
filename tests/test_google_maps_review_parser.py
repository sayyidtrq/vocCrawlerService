from datetime import datetime, timezone

from app.integrations.google_maps_review_parser import GoogleMapsReviewParser


def test_google_place_rating_snapshot_parsers():
    assert GoogleMapsReviewParser.parse_place_rating("4.3 9,422 reviews") == 4.3
    assert GoogleMapsReviewParser.parse_place_rating("Rating 4,8 dari 5") == 4.8
    assert GoogleMapsReviewParser.parse_place_rating("5 4 3 2 1") is None
    assert GoogleMapsReviewParser.parse_place_review_count("4.3 9,422 reviews") == 9422
    assert GoogleMapsReviewParser.parse_place_review_count("4,7 9.422 ulasan") == 9422
    assert GoogleMapsReviewParser.parse_place_review_count("4,7 9,4 rb ulasan") == 9400
    assert GoogleMapsReviewParser.parse_place_review_count("4.8 1.2k reviews") == 1200


def test_parse_review_full():
    scraped_at = datetime(2026, 9, 6, 10, 30, tzinfo=timezone.utc)
    raw = {
        "review_id": "review-123",
        "reviewer_name": "Dewi",
        "reviewer_meta": "Local Guide - 37 reviews",
        "rating_label": "5 stars",
        "review_text": "Excellent care.",
        "relative_time": "2 weeks ago",
        "profile_url": "https://google.com/maps/contrib/123",
        "photo_url": "https://example.com/dewi.jpg",
        "like_label": "12",
        "owner_text": "Thank you, Dewi.",
        "owner_time": "1 week ago",
    }

    assert GoogleMapsReviewParser.parse_review(
        raw,
        source_url="https://google.com/maps/place/example",
        scraped_at=scraped_at,
    ) == {
        "source": "selenium_google_maps",
        "external_review_id": "review-123",
        "reviewer_name": "Dewi",
        "reviewer_profile_url": "https://google.com/maps/contrib/123",
        "reviewer_photo_url": "https://example.com/dewi.jpg",
        "reviewer_local_guide_level": "Local Guide",
        "reviewer_total_reviews": 37,
        "rating": 5,
        "review_text": "Excellent care.",
        "review_relative_time": "2 weeks ago",
        "review_time": None,
        "review_language": "unknown",
        "language": "unknown",
        "like_count": 12,
        "owner_response_text": "Thank you, Dewi.",
        "owner_response_time": None,
        "scraped_at": "2026-09-06T10:30:00+00:00",
        "raw_payload": {
            "review_id": "review-123",
            "reviewer_name": "Dewi",
            "reviewer_meta": "Local Guide - 37 reviews",
            "rating_label": "5 stars",
            "review_text": "Excellent care.",
            "review_relative_time": "2 weeks ago",
            "like_label": "12",
            "owner_response_text": "Thank you, Dewi.",
            "owner_response_relative_time": "1 week ago",
            "source_url": "https://google.com/maps/place/example",
        },
    }


def test_parse_review_defaults():
    raw = {
        "review_id": None,
        "reviewer_name": None,
        "reviewer_meta": None,
        "rating_label": None,
        "review_text": None,
        "relative_time": None,
        "profile_url": None,
        "photo_url": None,
        "like_label": None,
        "owner_text": None,
        "owner_time": None,
    }

    review = GoogleMapsReviewParser.parse_review(
        raw,
        source_url="https://google.com/maps",
        scraped_at=datetime.now(timezone.utc),
    )

    assert review["reviewer_name"] == "Anonymous"
    assert review["reviewer_local_guide_level"] is None
    assert review["rating"] is None
    assert review["like_count"] == 0
    assert review["owner_response_text"] is None
    assert review["review_relative_time"] is None


def test_review_identity():
    assert GoogleMapsReviewParser.review_identity(
        {"external_review_id": " review-123 "}
    ) == "external:review-123"
    assert GoogleMapsReviewParser.review_identity(
        {
            "external_review_id": None,
            "reviewer_profile_url": "https://google.com/maps/contrib/123",
            "reviewer_name": " Dewi  Putri ",
            "rating": 5,
            "review_text": " Excellent  care. ",
        }
    ) == (
        "fallback:https://google.com/maps/contrib/123|Dewi Putri|5|Excellent care."
    )
