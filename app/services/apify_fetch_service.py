from __future__ import annotations

import functools
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Competitor
from app.db.session import get_session_factory
from app.integrations.apify_review_client import (
    ApifyReviewClient,
    ApifyRunIncompleteError,
)
from app.integrations.apify_token_pool import ApifyTokenPool
from app.integrations.review_source_client import ReviewSourceError
from app.services.apify_checkpoint_store import ApifyCheckpointStore
from app.services.competitor_review_service import CompetitorReviewService
from app.services.crawl_result import CrawlFetchResult, stop_reason
from app.services.crawl_target import CrawlTarget
from app.services.entitlement_service import EntitlementService
from app.services.fetch_log_service import FetchLogService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.utils.date_parser import is_within_date_range

logger = logging.getLogger(__name__)


class ApifyFetchService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: ApifyReviewClient | None = None,
        token_pool: ApifyTokenPool | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        self.location_service = LocationService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.review_service = ReviewService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.fetch_log_service = FetchLogService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.competitor_review_service = CompetitorReviewService(
            company_id=company_id, session_factory=self.session_factory
        )
        if client is None:
            pool = token_pool or ApifyTokenPool(self.settings.apify_api_tokens)
            client = ApifyReviewClient(
                self.settings,
                pool,
                ApifyCheckpointStore(self.session_factory),
            )
        self.client = client
        self.normalizer = FetchService(
            company_id=company_id,
            session_factory=self.session_factory,
            settings=self.settings,
            client=self.client,
        )

    def fetch_location(
        self,
        location_id: int,
        target: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
        sort_by: str = "newest",
    ) -> CrawlFetchResult:
        location = self.location_service.get_location(location_id)
        if location is None:
            raise ValueError("Location not found.")
        return self._run_fetch(
            CrawlTarget.from_location(location),
            target=target,
            date_from=date_from,
            date_to=date_to,
            on_progress=on_progress,
            sort_by=sort_by,
            insert_review=self.review_service.insert_review,
            enable_fetch_log=True,
        )

    def fetch_competitor(
        self,
        competitor_id: int,
        target: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
        sort_by: str = "newest",
    ) -> CrawlFetchResult:
        """Store competitor reviews without writing a location fetch log."""
        with self.session_factory() as session:
            statement = select(Competitor).where(Competitor.id == competitor_id)
            if self.company_id is not None:
                statement = statement.where(Competitor.company_id == self.company_id)
            competitor = session.scalar(statement)
            if competitor is None:
                raise ValueError("Competitor not found.")
            competitor_id_value = competitor.id
            crawl_target = CrawlTarget.from_competitor(competitor)
        return self._run_fetch(
            crawl_target,
            target=target,
            date_from=date_from,
            date_to=date_to,
            on_progress=on_progress,
            sort_by=sort_by,
            insert_review=functools.partial(
                self.competitor_review_service.insert_review, competitor_id_value
            ),
            enable_fetch_log=False,
        )

    def _run_fetch(
        self,
        crawl_target: CrawlTarget,
        *,
        target: int | None,
        date_from: datetime | None,
        date_to: datetime | None,
        on_progress,
        sort_by: str,
        insert_review,
        enable_fetch_log: bool,
    ) -> CrawlFetchResult:
        requested_target = self.validate_target(
            target or crawl_target.target_review_count
        )
        result: CrawlFetchResult = {
            f"{crawl_target.kind}_id": crawl_target.id,
            f"{crawl_target.kind}_name": crawl_target.branch_name,
            "source": self.client.source_name,
            "status": "failed",
            "target_review_count": requested_target,
            "total_fetched": 0,
            "total_inserted": 0,
            "total_duplicate": 0,
            "total_failed": 0,
            "total_skipped_out_of_range": 0,
            "error_message": None,
            "metadata": {
                "target_review_count": requested_target,
                "max_reviews_to_collect": requested_target,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        }
        log_id = None
        if enable_fetch_log:
            log_id = self.fetch_log_service.start_log(
                crawl_target.id, self.client.source_name, result["metadata"]
            )
        logger.info(
            "Apify fetch started for %s with target %s",
            crawl_target.branch_name,
            requested_target,
        )
        try:
            if on_progress is not None:
                on_progress(0, requested_target, 0)
            raw_reviews = self.client.fetch_reviews(
                crawl_target,
                limit=requested_target,
                sort_by=sort_by,
                date_from=date_from,
                date_to=date_to,
            )
            if on_progress is not None:
                on_progress(len(raw_reviews), requested_target, len(raw_reviews))
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"].update(
                {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "sort_forced_to_newest": False,
                    "max_reviews_to_collect": requested_target,
                }
            )
            result["total_fetched"] = len(raw_reviews)
            result["total_failed"] = int(
                result["metadata"].get("failed_review_cards", 0)
            )
            self._store_reviews(
                crawl_target, raw_reviews, date_from, date_to, insert_review, result
            )

            stored = result["total_inserted"] + result["total_duplicate"]
            partial = (
                result["metadata"].get("stopped_reason") == "apify_accounts_exhausted"
                or (
                    stored < requested_target
                    and result["total_skipped_out_of_range"] == 0
                )
                or result["total_failed"] > 0
            )
            result["status"] = "partial_success" if partial else "success"
            public_stop_reason = stop_reason(result)
            if public_stop_reason:
                result["metadata"]["stop_reason"] = public_stop_reason
        except ApifyRunIncompleteError as exc:
            # Apify never confirmed this run SUCCEEDED. Store whatever
            # reviews it did have - real data, not wasted - but do NOT
            # report this as partial_success: that status is terminal, and
            # OneBox would read it as "this target is done". Without a
            # confirmed SUCCEEDED we can't vouch for that, so this stays a
            # retriable failure. A checkpoint was already saved by the
            # client before raising, so the retry resumes from here instead
            # of re-scraping the whole place (that's the actual fix for
            # wasting API calls - not declaring victory early).
            if on_progress is not None:
                on_progress(len(exc.reviews), requested_target, len(exc.reviews))
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"].update(
                {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "failure_code": exc.code,
                    "retriable": True,
                }
            )
            result["total_fetched"] = len(exc.reviews)
            self._store_reviews(
                crawl_target, exc.reviews, date_from, date_to, insert_review, result
            )
            result["status"] = "failed"
            result["error_message"] = str(exc)
            logger.warning(
                "Apify run incomplete for %s: %s (kept %s reviews, will "
                "retry from checkpoint)",
                crawl_target.branch_name,
                exc,
                len(exc.reviews),
            )
        except ReviewSourceError as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            result["metadata"]["failure_code"] = exc.code
            result["metadata"]["retriable"] = exc.retriable
            logger.warning(
                "Apify review source rejected %s: %s", crawl_target.branch_name, exc
            )
        except Exception as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            logger.exception("Apify fetch failed for %s", crawl_target.branch_name)
        finally:
            if enable_fetch_log:
                self.fetch_log_service.finish_log(log_id, result)
        return result

    def _store_reviews(
        self,
        crawl_target: CrawlTarget,
        raw_reviews: list[dict],
        date_from: datetime | None,
        date_to: datetime | None,
        insert_review,
        result: CrawlFetchResult,
    ) -> None:
        for raw_review in raw_reviews:
            try:
                normalized = self.normalizer.normalize_review(
                    crawl_target, raw_review
                )
                if not is_within_date_range(
                    normalized["review_time"], date_from, date_to
                ):
                    result["total_skipped_out_of_range"] += 1
                    key = (
                        "out_of_range_older"
                        if self._is_older_than_range(
                            normalized["review_time"], date_from
                        )
                        else "out_of_range_newer"
                    )
                    result["metadata"][key] = int(result["metadata"].get(key) or 0) + 1
                    continue
                _, duplicate = insert_review(normalized)
                if duplicate:
                    result["total_duplicate"] += 1
                else:
                    result["total_inserted"] += 1
            except Exception:
                result["total_failed"] += 1
                logger.exception("Failed to store one Apify review")

    def validate_target(self, target: object) -> int:
        try:
            value = int(target)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        maximum = min(self.settings.crawl_max_target_reviews, 300)
        if self.company_id is not None:
            quota = EntitlementService(
                self.company_id, self.session_factory
            ).review_quota()
            if quota > 0:
                maximum = min(maximum, quota)
        if not 1 <= value <= maximum:
            raise ValueError(f"Target review count must be between 1 and {maximum}.")
        return value

    @staticmethod
    def _is_older_than_range(
        review_time: datetime | None, date_from: datetime | None
    ) -> bool:
        if review_time is None or date_from is None:
            return False
        try:
            return review_time < date_from
        except TypeError:
            return False
