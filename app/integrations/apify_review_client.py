from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.integrations.apify_client import ApifyAccountExhaustedError, ApifyClient
from app.integrations.apify_review_parser import ApifyReviewParser
from app.integrations.apify_token_pool import (
    ApifyAllAccountsExhaustedError,
    ApifyTokenPool,
)
from app.integrations.review_source_client import ReviewSourceClient, ReviewSourceError
from app.utils.date_parser import parse_datetime

# web_wanderer/google-reviews-scraper's `order` input, confirmed against its
# published input schema for the first three values. "lowest_rating" is not
# documented on this actor at all - kept as a best-guess snake_case value
# consistent with the other three until verified against a real run; if the
# actor rejects it, CrawlTargetRequest.sort_by="lowest_rating" will surface
# that as an APIFY_RUN_FAILED error rather than silently sorting wrong.
SORT_BY_MAP = {
    "newest": "newest",
    "most_relevant": "most_relevant",
    "highest_rating": "highest_rating",
    "lowest_rating": "lowest_rating",
}


class ApifyReviewClient(ReviewSourceClient):
    source_name = "apify_google_maps"

    def __init__(
        self,
        settings: Settings,
        token_pool: ApifyTokenPool,
        checkpoint_store,
        apify_client: ApifyClient | None = None,
    ):
        self.settings = settings
        self.token_pool = token_pool
        self.checkpoint_store = checkpoint_store
        self.apify_client = apify_client or ApifyClient(settings)
        self.last_metadata: dict = {}

    def fetch_reviews(
        self,
        crawl_target,
        limit: int,
        sort_by: str = "newest",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        del date_to  # Apify has no actor-side upper bound.
        if sort_by not in SORT_BY_MAP:
            raise ReviewSourceError(
                f"Unsupported review sort: {sort_by}.",
                code="APIFY_INVALID_SORT",
            )
        place_id = (crawl_target.external_place_id or "").strip()
        if not place_id:
            raise ReviewSourceError(
                "External Place ID is required for Apify.",
                code="APIFY_PLACE_ID_REQUIRED",
            )

        effective_sort, lower_bound = (
            self.checkpoint_store.resolve_effective_lower_bound(
                crawl_target, sort_by, date_from
            )
        )
        self.last_metadata = {
            "target_review_count": limit,
            "max_reviews_to_collect": limit,
            "sort_by": effective_sort,
            "sort_applied": True,
            "reviews_scanned": 0,
            "matched_review_cards": 0,
            "failed_review_cards": 0,
        }
        reviews: list[dict] = []
        seen_review_ids: set[str] = set()
        last_review: dict | None = None
        exhausted = False

        while len(reviews) < limit:
            try:
                token = self.token_pool.current()
                actor_input = {
                    "place_ids": [place_id],
                    "limit": limit,
                    "order": SORT_BY_MAP[effective_sort],
                    # "Googles" (not "google") per the actor's published
                    # input schema - unconfirmed against a live run, verify
                    # once a real token exists (see migration doc's
                    # verification checklist).
                    "source": "Googles",
                }
                if lower_bound is not None:
                    # anyDate wants YYYY-MM-DD, not a full ISO timestamp.
                    actor_input["anyDate"] = lower_bound.date().isoformat()

                run_id, dataset_id = self.apify_client.start_run(
                    self.settings.apify_actor_id, actor_input, token=token
                )
                self.last_metadata.update(
                    {
                        "apify_run_id": run_id,
                        "apify_dataset_id": dataset_id,
                        "apify_account_index_used": self.token_pool.current_index,
                    }
                )
                status = self.apify_client.get_run_status(run_id, token=token)
                if status != "SUCCEEDED":
                    raise ReviewSourceError(
                        f"Apify actor run ended with status {status}.",
                        retriable=True,
                        code="APIFY_RUN_FAILED",
                    )

                for item in self.apify_client.iter_dataset_items(
                    dataset_id, token=token
                ):
                    parsed = ApifyReviewParser.parse_review(item)
                    last_review = parsed
                    self._capture_place_metadata(item)
                    self.last_metadata["reviews_scanned"] += 1
                    review_id = str(parsed.get("external_review_id") or "")
                    if review_id and review_id in seen_review_ids:
                        continue
                    if review_id:
                        seen_review_ids.add(review_id)
                    reviews.append(parsed)
                    if len(reviews) >= limit:
                        break

                self.checkpoint_store.clear(crawl_target)
                break
            except ApifyAccountExhaustedError:
                if last_review is not None:
                    lower_bound = (
                        parse_datetime(last_review.get("review_time")) or lower_bound
                    )
                try:
                    if self.token_pool.rotate() is None:
                        raise ApifyAllAccountsExhaustedError(
                            "All configured Apify accounts are exhausted."
                        )
                except ApifyAllAccountsExhaustedError:
                    exhausted = True
                    break
            except ApifyAllAccountsExhaustedError:
                exhausted = True
                break

        if exhausted:
            self.last_metadata["stopped_reason"] = "apify_accounts_exhausted"
            if last_review is not None:
                review_time = parse_datetime(last_review.get("review_time"))
                review_id = last_review.get("external_review_id")
                if review_time is not None and review_id:
                    from app.services.apify_checkpoint_store import ApifyCheckpoint

                    self.checkpoint_store.save(
                        crawl_target,
                        ApifyCheckpoint(
                            sort_by=effective_sort,
                            review_time=review_time,
                            review_id=str(review_id),
                            recorded_at=datetime.now(timezone.utc),
                        ),
                    )
        self.last_metadata["matched_review_cards"] = len(reviews)
        self.last_metadata["scraped_review_cards"] = len(reviews)
        return reviews

    def _capture_place_metadata(self, item: dict) -> None:
        if "place_rating" not in self.last_metadata:
            self.last_metadata["place_rating"] = item.get("place_rating")
            self.last_metadata["place_review_count"] = item.get("place_reviews_count")
            self.last_metadata["rating_snapshot_at"] = item.get("scraped_at")
            self.last_metadata["rating_snapshot"] = {
                "source": "google_maps",
                "place_rating": item.get("place_rating"),
                "place_review_count": item.get("place_reviews_count"),
                "snapshot_at": item.get("scraped_at"),
            }
