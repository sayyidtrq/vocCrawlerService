from __future__ import annotations

from datetime import datetime, timezone
import logging
import time

from app.config import Settings
from app.integrations.apify_client import ApifyAccountExhaustedError, ApifyClient
from app.integrations.apify_review_parser import ApifyReviewParser
from app.integrations.apify_token_pool import (
    ApifyAllAccountsExhaustedError,
    ApifyTokenPool,
)
from app.integrations.review_source_client import ReviewSourceClient, ReviewSourceError
from app.utils.date_parser import parse_datetime

logger = logging.getLogger(__name__)

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


class ApifyRunIncompleteError(ReviewSourceError):
    """Apify never confirmed this run SUCCEEDED - the run failed, was
    aborted, or our own patience for polling ran out.

    Carries whatever reviews the dataset already had (real data, since
    Apify pushes items incrementally as the actor scrapes) so the caller can
    still store them, but is deliberately NOT treated as a completed fetch:
    without a confirmed SUCCEEDED we have no basis to tell OneBox this
    target is done. retriable=True lets CrawlWorker retry. The retry repeats
    the same window - the actor has no offset, so there is no cheap resume
    (spec B13); reviews already stored are skipped as duplicates.
    """

    def __init__(
        self,
        message: str,
        *,
        reviews: list[dict],
        code: str,
        retriable: bool = True,
    ):
        super().__init__(message, retriable=retriable, code=code)
        self.reviews = reviews


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
        self._last_drained: dict | None = None

    def fetch_reviews(
        self,
        crawl_target,
        limit: int,
        sort_by: str = "newest",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        del date_to  # Apify has no actor-side upper bound.
        place_id, effective_sort, lower_bound = self._prepare(
            crawl_target, limit, sort_by, date_from
        )
        reviews: list[dict] = []
        seen_review_ids: set[str] = set()
        last_review: dict | None = None
        exhausted = False
        rotations = 0
        max_rotations = len(self.token_pool._tokens) if self.token_pool._tokens else 1

        while len(reviews) < limit:
            try:
                token = self.token_pool.current()
                actor_input = self._actor_input(
                    place_id, limit, effective_sort, lower_bound
                )

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

                self._last_drained = last_review
                try:
                    self._drain(dataset_id, token, limit, reviews, seen_review_ids)
                finally:
                    # Tetap terbaca walau akun habis di tengah dataset.
                    last_review = self._last_drained

                if status == "SUCCEEDED":
                    self.checkpoint_store.clear(crawl_target)
                    break

                # The run didn't confirm SUCCEEDED (Apify reported it
                # failed/aborted/timed out, or we gave up waiting for a
                # terminal status - see ApifyClient.get_run_status). Without
                # a confirmed SUCCEEDED we have no basis to tell OneBox this
                # target is done, even if we already have some reviews in
                # hand - Apify itself hasn't vouched for this being the
                # complete picture. Record where it stopped (the checkpoint is
                # a record, not a resume point - spec B13), keep whatever
                # reviews the dataset already had (real data, worth storing
                # either way), and raise retriable so the job stays open
                # rather than resolving as a false "finished".
                self._save_checkpoint(crawl_target, effective_sort, last_review)
                self.last_metadata["matched_review_cards"] = len(reviews)
                self.last_metadata["scraped_review_cards"] = len(reviews)
                self.last_metadata["collected_unique"] = len(seen_review_ids)
                raise ApifyRunIncompleteError(
                    f"Apify actor run ended with status {status}.",
                    reviews=reviews,
                    code=f"APIFY_RUN_{status.replace('-', '_')}",
                )
            except ApifyAccountExhaustedError as exc:
                # Batas bawah sengaja TIDAK dimajukan ke review terakhir (spec
                # B13): itu review tertua yang terbaca, jadi memajukannya akan
                # melompati review yang belum terbaca. Akun berikutnya mengulang
                # jendela yang sama; review yang sudah ada dilewati lewat
                # seen_review_ids.
                rotations += 1
                try:
                    self._rotate_account(
                        crawl_target, effective_sort, last_review, exc
                    )
                    if rotations >= max_rotations:
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
            self._save_checkpoint(crawl_target, effective_sort, last_review)
        self.last_metadata["matched_review_cards"] = len(reviews)
        self.last_metadata["scraped_review_cards"] = len(reviews)
        self.last_metadata["collected_unique"] = len(seen_review_ids)
        return reviews

    def _prepare(self, crawl_target, limit: int, sort_by: str, date_from):
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
        return place_id, effective_sort, lower_bound

    @staticmethod
    def _actor_input(place_id: str, limit: int, effective_sort: str, lower_bound) -> dict:
        actor_input = {
            "place_ids": [place_id],
            "limit": limit,
            "order": SORT_BY_MAP[effective_sort],
            # Defaults to false on the actor, which returns every review with
            # reviewer_name/reviewer_id/reviewer_url nulled out - verified
            # across 2920 real records from three places, all of them
            # anonymous, so a VoC ticket raised from a complaint had no
            # customer on it.
            "include_personal": True,
            # Confirmed against a real 400 error from the actor: valid values
            # are "all", "google", "tripadvisor", "trip_com", "priceline",
            # "zenhotels" - lowercase "google", not "Googles" as an earlier
            # docs-page summary had it.
            "source": "google",
        }
        if lower_bound is not None:
            # anyDate wants YYYY-MM-DD, not a full ISO timestamp.
            actor_input["anyDate"] = lower_bound.date().isoformat()
        return actor_input

    def _drain(
        self,
        dataset_id: str,
        token: str,
        limit: int,
        reviews: list[dict],
        seen_review_ids: set[str],
    ) -> None:
        """Baca dataset ke `reviews`, lewati id ganda.

        Item terakhir yang terbaca disimpan di self._last_drained, bukan
        dikembalikan, supaya tetap ada ketika iterasi dihentikan exception.
        """
        for item in self.apify_client.iter_dataset_items(dataset_id, token=token):
            parsed = ApifyReviewParser.parse_review(item)
            self._last_drained = parsed
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

    # --- run yang diparkir (spec CS-3) -------------------------------------

    def start_fetch(
        self, crawl_target, limit: int, sort_by: str = "newest", date_from=None
    ) -> dict:
        """Mulai run Apify tanpa menunggunya. Kembalikan handle yang JSON-aman.

        Akun yang habis dirotasi di sini; bila semua habis, error-nya naik ke
        pemanggil (ApifyAllAccountsExhaustedError).
        """
        self.last_metadata = {}
        place_id, effective_sort, lower_bound = self._prepare(
            crawl_target, limit, sort_by, date_from
        )
        actor_input = self._actor_input(place_id, limit, effective_sort, lower_bound)
        account_switch = None
        last_exc = None
        for attempt in range(10):
            try:
                token = self.token_pool.current()
            except ApifyAllAccountsExhaustedError as exc:
                raise ApifyAllAccountsExhaustedError(
                    "All configured Apify accounts are exhausted."
                ) from exc
            try:
                run_id, dataset_id = self.apify_client.start_run(
                    self.settings.apify_actor_id, actor_input, token=token
                )
                handle = {
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "token_index": self.token_pool.current_index,
                    "effective_sort": effective_sort,
                    "limit": limit,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "actor_input": actor_input,
                }
                if account_switch is not None:
                    handle["account_switch"] = account_switch
                return handle
            except Exception as exc:
                last_exc = exc
                if isinstance(exc, ApifyAccountExhaustedError):
                    self.token_pool.mark_exhausted(self.token_pool.current_index)
                logger.warning(
                    "Apify start_run attempt %d/10 failed for %s: %s; rotating token and retrying",
                    attempt + 1,
                    getattr(crawl_target, "branch_name", str(crawl_target)),
                    exc,
                )
                time.sleep(min(3.0, 0.5 * (attempt + 1)))
                try:
                    self._rotate_account(
                        crawl_target,
                        effective_sort,
                        None,
                        exc if isinstance(exc, ApifyAccountExhaustedError) else None,
                    )
                except ApifyAllAccountsExhaustedError:
                    break
                account_switch = self.token_pool.last_switch

        if isinstance(last_exc, ApifyAccountExhaustedError):
            raise ApifyAllAccountsExhaustedError("All configured Apify accounts are exhausted.") from last_exc
        raise last_exc

    def poll_fetch(self, handle: dict) -> tuple[str, int | None]:
        """(status, jumlah item dataset sejauh ini) tanpa menunggu."""
        token = self.token_pool.token_at(int(handle["token_index"]))
        status = self.apify_client.get_run_status_once(handle["run_id"], token=token)
        try:
            count = self.apify_client.dataset_item_count(
                handle["dataset_id"], token=token
            )
        except ReviewSourceError:
            count = None  # kemajuan bersifat kosmetik
        return status, count

    def restart_fetch_after_exhaustion(
        self,
        crawl_target,
        handle: dict,
        error: ApifyAccountExhaustedError,
    ) -> dict:
        """Repeat the exact actor input with the next available account."""
        self.token_pool.mark_exhausted(int(handle.get("token_index", self.token_pool.current_index)))
        effective_sort = str(handle["effective_sort"])
        actor_input = dict(handle["actor_input"])
        rotations = 0
        max_rotations = len(self.token_pool._tokens) if self.token_pool._tokens else 1
        while True:
            rotations += 1
            if rotations > max_rotations:
                raise ApifyAllAccountsExhaustedError(
                    "All configured Apify accounts are exhausted."
                ) from error
            try:
                self._rotate_account(crawl_target, effective_sort, None, error)
            except ApifyAllAccountsExhaustedError:
                raise
            try:
                token = self.token_pool.current()
            except ApifyAllAccountsExhaustedError:
                raise
            try:
                run_id, dataset_id = self.apify_client.start_run(
                    self.settings.apify_actor_id, actor_input, token=token
                )
            except ApifyAccountExhaustedError as next_error:
                error = next_error
                self.token_pool.mark_exhausted(self.token_pool.current_index)
                continue
            return {
                **handle,
                "run_id": run_id,
                "dataset_id": dataset_id,
                "token_index": self.token_pool.current_index,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "account_switch": self.token_pool.last_switch,
            }

    def abort_fetch(self, handle: dict) -> None:
        token = self.token_pool.token_at(int(handle["token_index"]))
        self.apify_client.abort_run(handle["run_id"], token=token)

    def finish_fetch(self, crawl_target, handle: dict, status: str) -> list[dict]:
        """Kuras dataset run yang sudah berhenti; sama dengan jalur sinkron."""
        limit = int(handle["limit"])
        effective_sort = handle["effective_sort"]
        self.last_metadata = {
            "target_review_count": limit,
            "max_reviews_to_collect": limit,
            "sort_by": effective_sort,
            "sort_applied": True,
            "reviews_scanned": 0,
            "matched_review_cards": 0,
            "failed_review_cards": 0,
            "apify_run_id": handle["run_id"],
            "apify_dataset_id": handle["dataset_id"],
            "apify_account_index_used": handle["token_index"],
        }
        if isinstance(handle.get("account_switch"), dict):
            self.last_metadata["apify_account_switch"] = handle["account_switch"]
        token = self.token_pool.token_at(int(handle["token_index"]))
        reviews: list[dict] = []
        seen_review_ids: set[str] = set()
        self._last_drained = None
        try:
            self._drain(handle["dataset_id"], token, limit, reviews, seen_review_ids)
        except ApifyAccountExhaustedError as exc:
            self.token_pool.mark_exhausted(int(handle.get("token_index", self.token_pool.current_index)))
            next_token = self._rotate_account(
                crawl_target, effective_sort, self._last_drained, exc
            )
            if next_token is None:
                self.last_metadata["stopped_reason"] = "apify_accounts_exhausted"
            else:
                raise ApifyRunIncompleteError(
                    "Apify account ran out of credits while reading its dataset.",
                    reviews=reviews,
                    code="APIFY_ACCOUNT_SWITCHED",
                ) from exc
        last_review = self._last_drained
        self.last_metadata["matched_review_cards"] = len(reviews)
        self.last_metadata["scraped_review_cards"] = len(reviews)
        self.last_metadata["collected_unique"] = len(seen_review_ids)
        if status == "SUCCEEDED":
            if self.last_metadata.get("stopped_reason") != (
                "apify_accounts_exhausted"
            ):
                self.checkpoint_store.clear(crawl_target)
            return reviews
        self._save_checkpoint(crawl_target, effective_sort, last_review)
        raise ApifyRunIncompleteError(
            f"Apify actor run ended with status {status}.",
            reviews=reviews,
            code=f"APIFY_RUN_{status.replace('-', '_')}",
        )

    def _rotate_account(
        self,
        crawl_target,
        effective_sort: str,
        last_review: dict | None,
        error: ApifyAccountExhaustedError | None = None,
    ) -> str | None:
        if error is not None:
            self.token_pool.mark_exhausted(self.token_pool.current_index)
        marker = {
            "target_kind": getattr(crawl_target, "kind", "location"),
            "target_id": crawl_target.id,
            "request": getattr(error, "request", None),
            "response": getattr(error, "response", None),
        }
        next_token = self.token_pool.rotate(marker)
        if next_token is None:
            raise ApifyAllAccountsExhaustedError("All configured Apify accounts are exhausted.")
        switch = self.token_pool.last_switch
        if switch is not None:
            self.last_metadata["apify_account_switch"] = switch
        self._save_checkpoint(
            crawl_target,
            effective_sort,
            last_review,
            account_switch=switch,
        )
        return next_token

    def _save_checkpoint(
        self,
        crawl_target,
        effective_sort: str,
        last_review: dict | None,
        *,
        account_switch: dict | None = None,
    ) -> None:
        review_time = (
            parse_datetime(last_review.get("review_time")) if last_review else None
        )
        review_id = last_review.get("external_review_id") if last_review else None
        previous = self.checkpoint_store.load(crawl_target)
        if review_time is None or not review_id:
            review_time = previous.review_time if previous else None
            review_id = previous.review_id if previous else None
        if account_switch is None and previous is not None:
            account_switch = previous.account_switch
        if review_time is None and account_switch is None:
            return
        from app.services.apify_checkpoint_store import ApifyCheckpoint

        self.checkpoint_store.save(
            crawl_target,
            ApifyCheckpoint(
                sort_by=effective_sort,
                recorded_at=datetime.now(timezone.utc),
                review_time=review_time,
                review_id=str(review_id) if review_id else None,
                account_switch=account_switch,
            ),
        )

    def _capture_place_metadata(self, item: dict) -> None:
        if "place_rating" not in self.last_metadata:
            self.last_metadata["place_rating"] = item.get("place_rating")
            self.last_metadata["place_review_count"] = item.get("place_reviews_count")
            self.last_metadata["expected_review_count"] = item.get(
                "place_reviews_count"
            )
            self.last_metadata["rating_snapshot_at"] = item.get("scraped_at")
            self.last_metadata["rating_snapshot"] = {
                "source": "google_maps",
                "place_rating": item.get("place_rating"),
                "place_review_count": item.get("place_reviews_count"),
                "snapshot_at": item.get("scraped_at"),
            }
