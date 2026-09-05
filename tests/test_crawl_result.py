import pytest

from app.services.crawl_result import (
    matched_count,
    rating_snapshot,
    scanned_count,
    stop_reason,
)


@pytest.mark.parametrize(
    ("internal", "public"),
    [
        ("out_of_range", "older_than_window"),
        ("time_limit", "timeout"),
        ("no_new_review_cards", "no_more_reviews"),
    ],
)
def test_stop_reason_maps_internal_reasons(internal, public):
    assert stop_reason({"metadata": {"stop_reason": internal}}) == public


def test_stop_reason_passes_through_unmapped_value():
    assert stop_reason({"metadata": {"stop_reason": "target_reached"}}) == (
        "target_reached"
    )


def test_stop_reason_falls_back_to_stopped_reason():
    assert stop_reason({"metadata": {"stopped_reason": "time_limit"}}) == "timeout"


def test_stop_reason_returns_none_without_metadata():
    assert stop_reason({}) is None


def test_rating_snapshot_returns_existing_dict_as_is():
    snapshot = {
        "source": "google_maps",
        "place_rating": 4.8,
        "place_review_count": 125,
        "snapshot_at": "2026-09-05T10:00:00+07:00",
    }

    assert rating_snapshot({"metadata": {"rating_snapshot": snapshot}}) is snapshot


def test_rating_snapshot_builds_from_metadata():
    assert rating_snapshot(
        {
            "metadata": {
                "place_rating": 4.7,
                "place_review_count": 120,
                "rating_snapshot_at": "2026-09-05T10:00:00+07:00",
            }
        }
    ) == {
        "source": "google_maps",
        "place_rating": 4.7,
        "place_review_count": 120,
        "snapshot_at": "2026-09-05T10:00:00+07:00",
    }


def test_rating_snapshot_returns_none_without_rating_data():
    assert rating_snapshot({}) is None


def test_scanned_count_uses_metadata_reviews_scanned():
    assert scanned_count(
        {"total_fetched": 5, "metadata": {"reviews_scanned": 12}}
    ) == 12


def test_scanned_count_falls_back_to_total_fetched():
    assert scanned_count({"total_fetched": 5}) == 5


def test_matched_count_uses_metadata_matched_review_cards():
    assert matched_count(
        {"total_fetched": 5, "metadata": {"matched_review_cards": 3}}
    ) == 3


def test_matched_count_subtracts_out_of_range_from_total_fetched():
    assert matched_count(
        {"total_fetched": 5, "total_skipped_out_of_range": 2}
    ) == 3
