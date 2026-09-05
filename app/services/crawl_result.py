from __future__ import annotations

from typing import Required, TypedDict


class RatingSnapshot(TypedDict):
    source: str
    place_rating: float | None
    place_review_count: int | None
    snapshot_at: str | None


class CrawlRequestSnapshot(TypedDict):
    crawl_mode: str
    max_reviews_to_collect: int
    scan_limit: int
    dry_run: bool
    date_from: str | None
    date_to: str | None
    sort_by: str


class CrawlResultMetadata(TypedDict, total=False):
    target_review_count: int
    max_reviews_to_collect: int
    scan_limit: int
    loaded_review_cards: int
    scraped_review_cards: int
    failed_review_cards: int
    scroll_attempts: int
    headless: bool
    url: str
    final_url: str
    url_strategy: str
    fallback_from_url: str | None
    stopped_reason: str | None
    stop_reason: str
    sort_by: str
    sort_applied: bool
    time_limit_seconds: int
    reviews_scanned: int
    place_rating: float | None
    place_review_count: int | None
    rating_snapshot_at: str | None
    rating_snapshot: RatingSnapshot
    date_from: str | None
    date_to: str | None
    sort_forced_to_newest: bool
    range_warning: str
    out_of_range_older: int
    out_of_range_newer: int
    crawl_mode: str
    # Never written anywhere; matched_count permanently falls back when absent.
    matched_review_cards: int


class CrawlFetchResult(TypedDict, total=False):
    location_id: int
    location_name: str
    competitor_id: int
    competitor_name: str
    source: Required[str]
    status: Required[str]  # "success" | "partial_success" | "failed"
    target_review_count: Required[int]
    total_fetched: Required[int]
    total_inserted: Required[int]
    total_duplicate: Required[int]
    total_failed: Required[int]
    total_skipped_out_of_range: Required[int]
    error_message: Required[str | None]
    metadata: Required[CrawlResultMetadata]


def stop_reason(result: dict) -> str | None:
    metadata = result.get("metadata") or {}
    reason = metadata.get("stop_reason") or metadata.get("stopped_reason")
    mapping = {
        "out_of_range": "older_than_window",
        "time_limit": "timeout",
        "no_new_review_cards": "no_more_reviews",
    }
    return mapping.get(reason, reason)


def rating_snapshot(result: dict) -> RatingSnapshot | None:
    metadata = result.get("metadata") or {}
    snapshot = metadata.get("rating_snapshot")
    if isinstance(snapshot, dict):
        return snapshot
    rating = metadata.get("place_rating") or result.get("place_rating")
    review_count = metadata.get("place_review_count") or result.get(
        "place_review_count"
    )
    snapshot_at = metadata.get("rating_snapshot_at") or result.get(
        "rating_snapshot_at"
    )
    if rating is None and review_count is None and snapshot_at is None:
        return None
    return {
        "source": "google_maps",
        "place_rating": rating,
        "place_review_count": review_count,
        "snapshot_at": snapshot_at,
    }


def scanned_count(result: dict) -> int:
    metadata = result.get("metadata") or {}
    fetched_count = int(result.get("total_fetched") or 0)
    count = metadata.get("reviews_scanned")
    if count is None:
        count = (
            result.get("reviews_scanned")
            or result.get("progress_scanned")
            or metadata.get("loaded_review_cards")
            or fetched_count
            or result.get("progress_fetched")
            or 0
        )
    return int(count)


def matched_count(result: dict) -> int:
    metadata = result.get("metadata") or {}
    fetched_count = int(result.get("total_fetched") or 0)
    out_of_range_count = int(result.get("total_skipped_out_of_range") or 0)
    return int(
        metadata.get("matched_review_cards")
        if metadata.get("matched_review_cards") is not None
        else max(0, fetched_count - out_of_range_count)
    )
