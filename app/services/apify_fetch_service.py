from __future__ import annotations

import functools
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Competitor
from app.db.session import get_session_factory
from app.integrations.apify_review_client import (
    ApifyReviewClient,
    ApifyRunIncompleteError,
)
from app.integrations.apify_token_pool import (
    ApifyAllAccountsExhaustedError,
    ApifyTokenPool,
)
from app.integrations.review_source_client import ReviewSourceError
from app.services.apify_checkpoint_store import ApifyCheckpointStore
from app.services.competitor_review_service import CompetitorReviewService
from app.services.crawl_coverage import CrawlCoverageStore
from app.services.crawl_result import CrawlFetchResult
from app.services.crawl_target import CrawlTarget
from app.services.entitlement_service import EntitlementService
from app.services.fetch_log_service import FetchLogService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.utils.date_parser import is_within_date_range_approx

logger = logging.getLogger(__name__)

DEADLINE_CODE = "APIFY_RUN_DEADLINE_EXCEEDED"
_SOURCE_TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


class ApifyFetchService:
    # CrawlWorker hanya memarkir run untuk layanan yang mendukungnya.
    supports_parking = True

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
        self.coverage_store = CrawlCoverageStore(self.session_factory)
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
        coverage: str | None = None,
        budget: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
        sort_by: str = "newest",
        review_quota_remaining: int | None = None,
        park: bool = False,
        source_run: dict | None = None,
    ) -> CrawlFetchResult:
        location = self.location_service.get_location(location_id)
        if location is None:
            raise ValueError("Location not found.")
        return self._dispatch(
            CrawlTarget.from_location(location),
            park=park,
            source_run=source_run,
            target=target,
            coverage=coverage or "delta",
            budget=budget,
            new_contract=coverage is not None or budget is not None,
            date_from=date_from,
            date_to=date_to,
            on_progress=on_progress,
            sort_by=sort_by,
            insert_review=self.review_service.insert_review,
            review_exists=self.review_service.review_exists,
            review_quota_remaining=review_quota_remaining,
            enable_fetch_log=True,
        )

    def fetch_competitor(
        self,
        competitor_id: int,
        target: int | None = None,
        coverage: str | None = None,
        budget: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
        sort_by: str = "newest",
        review_quota_remaining: int | None = None,
        park: bool = False,
        source_run: dict | None = None,
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
        return self._dispatch(
            crawl_target,
            park=park,
            source_run=source_run,
            target=target,
            coverage=coverage or "delta",
            budget=budget,
            new_contract=coverage is not None or budget is not None,
            date_from=date_from,
            date_to=date_to,
            on_progress=on_progress,
            sort_by=sort_by,
            insert_review=functools.partial(
                self.competitor_review_service.insert_review, competitor_id_value
            ),
            review_exists=functools.partial(
                self.competitor_review_service.review_exists, competitor_id_value
            ),
            review_quota_remaining=review_quota_remaining,
            enable_fetch_log=False,
        )

    def _dispatch(self, crawl_target: CrawlTarget, *, park: bool,
                  source_run: dict | None, **run_kwargs):
        """Sinkron seperti dulu, atau lewat run yang diparkir (CS-3).

        Hasil parkir berbentuk {"parked": handle}; pemanggil (CrawlWorker)
        menyimpan handle itu dan mengklaim job lagi nanti.
        """
        if not park and source_run is None:
            return self._run_fetch(crawl_target, **run_kwargs)
        return self._parked_fetch(
            crawl_target,
            run_kwargs,
            source_run=source_run,
            on_progress=run_kwargs.get("on_progress"),
        )

    def _run_fetch(
        self,
        crawl_target: CrawlTarget,
        *,
        target: int | None,
        coverage: str = "delta",
        budget: int | None = None,
        new_contract: bool = False,
        date_from: datetime | None,
        date_to: datetime | None,
        on_progress,
        sort_by: str,
        insert_review,
        enable_fetch_log: bool,
        review_exists=None,
        review_quota_remaining: int | None = None,
        fetch_raw=None,
    ) -> CrawlFetchResult:
        requested_target, effective_from, swept = self._plan(
            crawl_target,
            target=target,
            coverage=coverage,
            budget=budget,
            new_contract=new_contract,
            date_from=date_from,
        )
        effective_budget = None if coverage == "date_window" else requested_target
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
                "coverage": coverage,
                "budget": effective_budget,
                "target_review_count": requested_target,
                "max_reviews_to_collect": requested_target,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        }
        now = datetime.now(timezone.utc)
        result["metadata"]["effective_date_from"] = (
            effective_from.isoformat() if effective_from else None
        )
        result["metadata"]["safety_sweep"] = swept
        stored_times: list = []
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
            if fetch_raw is None:
                raw_reviews = self.client.fetch_reviews(
                    crawl_target,
                    limit=requested_target,
                    sort_by=sort_by,
                    date_from=effective_from,
                    date_to=date_to,
                )
            else:
                raw_reviews = fetch_raw()
            if on_progress is not None:
                on_progress(len(raw_reviews), requested_target, len(raw_reviews))
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"].update(
                {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "sort_forced_to_newest": False,
                    "max_reviews_to_collect": requested_target,
                    "coverage": coverage,
                    "budget": effective_budget,
                    "effective_date_from": (
                        effective_from.isoformat() if effective_from else None
                    ),
                    "safety_sweep": swept,
                }
            )
            result["total_fetched"] = len(raw_reviews)
            result["total_failed"] = int(
                result["metadata"].get("failed_review_cards", 0)
            )
            quota_hit = self._store_reviews(
                crawl_target,
                raw_reviews,
                effective_from,
                date_to,
                insert_review,
                result,
                stored_times=stored_times,
                review_exists=review_exists,
                review_quota_remaining=review_quota_remaining,
            )

            expected = result["metadata"].get("expected_review_count")
            collected = result["metadata"].get("collected_unique")
            collected = len(raw_reviews) if collected is None else int(collected)
            exhausted = (
                result["metadata"].get("stopped_reason")
                == "apify_accounts_exhausted"
            )
            budget_reached = (
                effective_budget is not None and collected >= effective_budget
            )
            if coverage == "full_backfill":
                if expected is None:
                    completeness = "unknown"
                elif collected >= int(expected) * self.settings.crawl_completeness_tolerance:
                    completeness = "complete"
                else:
                    completeness = "partial"
            else:
                completeness = (
                    "partial" if exhausted or budget_reached else "complete"
                )
            if quota_hit:
                completeness = "partial"
            ratio = (
                round(collected / int(expected), 4)
                if expected not in {None, 0}
                else None
            )
            result["metadata"].update(
                {
                    "expected_review_count": expected,
                    "collected_unique": collected,
                    "completeness": completeness,
                    "completeness_ratio": ratio,
                }
            )
            stored = result["total_inserted"] + result["total_duplicate"]
            old_partial = (
                exhausted
                or (
                    stored < requested_target
                    and result["total_skipped_out_of_range"] == 0
                )
            )
            partial = (
                completeness == "partial"
                or (completeness == "unknown" and old_partial)
                or result["total_failed"] > 0
            )
            result["status"] = "partial_success" if partial else "success"
            if quota_hit:
                result["metadata"]["stop_reason"] = "review_quota_exhausted"
            elif exhausted:
                result["metadata"]["stop_reason"] = "source_quota_exhausted"
            elif budget_reached:
                result["metadata"]["stop_reason"] = "budget_exhausted"
            elif coverage == "delta" and result["total_inserted"] == 0:
                result["metadata"]["stop_reason"] = "no_new_reviews"
            elif completeness == "complete":
                result["metadata"]["stop_reason"] = "coverage_complete"
        except ApifyRunIncompleteError as exc:
            # Apify never confirmed this run SUCCEEDED. Store whatever
            # reviews it did have - real data, not wasted - but do NOT
            # report this as partial_success: that status is terminal, and
            # OneBox would read it as "this target is done". Without a
            # confirmed SUCCEEDED we can't vouch for that, so this stays a
            # retriable failure. The retry repeats the same window (no cheap
            # resume exists - spec B13); what is stored now comes back as
            # duplicates and costs nothing further on our side.
            if on_progress is not None:
                on_progress(len(exc.reviews), requested_target, len(exc.reviews))
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"].update(
                {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "failure_code": exc.code,
                    # Run yang melewati tenggat akan melewatinya lagi; jangan
                    # dibayar ulang otomatis.
                    "retriable": exc.code != DEADLINE_CODE,
                    "coverage": coverage,
                    "budget": effective_budget,
                    "stop_reason": (
                        "deadline_exceeded"
                        if exc.code == DEADLINE_CODE
                        else "source_not_confirmed"
                    ),
                }
            )
            result["total_fetched"] = len(exc.reviews)
            self._store_reviews(
                crawl_target,
                exc.reviews,
                effective_from,
                date_to,
                insert_review,
                result,
                stored_times=None,
                review_exists=review_exists,
                review_quota_remaining=review_quota_remaining,
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
            try:
                self._record_coverage(
                    crawl_target,
                    coverage=coverage,
                    result=result,
                    stored_times=stored_times,
                    date_from=date_from,
                    date_to=date_to,
                    swept=swept,
                    now=now,
                )
            except Exception:
                # Cakupan adalah catatan; kegagalannya tidak boleh
                # menggagalkan crawl yang datanya sudah tersimpan.
                logger.exception(
                    "Failed to record crawl coverage for %s", crawl_target.branch_name
                )
            if enable_fetch_log:
                self.fetch_log_service.finish_log(log_id, result)
        return result

    def _plan(
        self,
        crawl_target: CrawlTarget,
        *,
        target: int | None,
        coverage: str,
        budget: int | None,
        new_contract: bool,
        date_from: datetime | None,
    ) -> tuple[int, datetime | None, bool]:
        requested_target = self._resolve_actor_limit(
            crawl_target,
            target=target,
            coverage=coverage,
            budget=budget,
            new_contract=new_contract,
        )
        effective_from, swept = date_from, False
        if new_contract and coverage == "delta":
            effective_from, swept = self.coverage_store.delta_lower_bound(
                crawl_target,
                date_from,
                margin=timedelta(days=self.settings.crawl_watermark_margin_days),
                sweep_margin=timedelta(days=self.settings.crawl_safety_sweep_days),
                now=datetime.now(timezone.utc),
            )
        return requested_target, effective_from, swept

    def _parked_fetch(self, crawl_target: CrawlTarget, run_kwargs: dict, *,
                      source_run: dict | None, on_progress):
        """Jalur run yang diparkir (spec CS-3).

        Tanpa source_run: mulai run lalu kembalikan {"parked": handle}.
        Dengan source_run: cek sekali; masih jalan -> parkir lagi; sudah
        berhenti atau lewat tenggat -> selesaikan lewat _run_fetch biasa.
        """
        client = self.client
        if source_run is None:
            limit, effective_from, _ = self._plan(
                crawl_target,
                target=run_kwargs["target"],
                coverage=run_kwargs["coverage"],
                budget=run_kwargs["budget"],
                new_contract=run_kwargs["new_contract"],
                date_from=run_kwargs["date_from"],
            )
            try:
                handle = client.start_fetch(
                    crawl_target,
                    limit,
                    sort_by=run_kwargs["sort_by"],
                    date_from=effective_from,
                )
            except ApifyAllAccountsExhaustedError:
                def exhausted():
                    client.last_metadata["stopped_reason"] = "apify_accounts_exhausted"
                    client.last_metadata["collected_unique"] = 0
                    return []

                return self._run_fetch(crawl_target, fetch_raw=exhausted, **run_kwargs)
            except ReviewSourceError as exc:
                def rejected(error=exc):
                    raise error

                return self._run_fetch(crawl_target, fetch_raw=rejected, **run_kwargs)
            if on_progress is not None:
                on_progress(0, limit, 0)
            return {"parked": handle}

        status, count = client.poll_fetch(source_run)
        if status not in _SOURCE_TERMINAL:
            started = datetime.fromisoformat(source_run["started_at"])
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if elapsed < self.settings.apify_backfill_deadline_seconds:
                if on_progress is not None and count is not None:
                    on_progress(count, int(source_run["limit"]), count)
                return {"parked": source_run}
            try:
                client.abort_fetch(source_run)
            except ReviewSourceError:
                logger.warning("Could not abort Apify run %s", source_run["run_id"])
            status = DEADLINE_CODE.removeprefix("APIFY_RUN_")

        return self._run_fetch(
            crawl_target,
            fetch_raw=lambda: client.finish_fetch(crawl_target, source_run, status),
            **run_kwargs,
        )

    def _record_coverage(
        self,
        crawl_target: CrawlTarget,
        *,
        coverage: str,
        result: CrawlFetchResult,
        stored_times: list,
        date_from: datetime | None,
        date_to: datetime | None,
        swept: bool,
        now: datetime,
    ) -> None:
        metadata = result["metadata"]
        if result["status"] in {"success", "partial_success"}:
            # Hanya run yang berhasil boleh memajukan kursor (spec §4.5 no. 3).
            metadata["coverage_state"] = self.coverage_store.record_success(
                crawl_target,
                coverage=coverage,
                stored_times=stored_times,
                expected_review_count=metadata.get("expected_review_count"),
                complete=metadata.get("completeness") == "complete",
                swept=swept,
                now=now,
            )
        else:
            metadata["coverage_state"] = self.coverage_store.load(crawl_target)
        if coverage == "date_window":
            self.coverage_store.record_window(
                crawl_target,
                date_from=date_from,
                date_to=date_to,
                completeness=(
                    metadata.get("completeness")
                    if result["status"] != "failed"
                    else "partial"
                )
                or "partial",
                stop_reason=metadata.get("stop_reason"),
                now=now,
            )

    def _store_reviews(
        self,
        crawl_target: CrawlTarget,
        raw_reviews: list[dict],
        date_from: datetime | None,
        date_to: datetime | None,
        insert_review,
        result: CrawlFetchResult,
        *,
        stored_times: list | None = None,
        review_exists=None,
        review_quota_remaining: int | None = None,
    ) -> bool:
        """Simpan review; True bila kuota review bulanan OneBox habis di tengah."""
        quota_hit = False
        for raw_review in raw_reviews:
            try:
                normalized = self.normalizer.normalize_review(
                    crawl_target, raw_review
                )
                precision = normalized.get("review_time_precision")
                if not is_within_date_range_approx(
                    normalized["review_time"], precision, date_from, date_to
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
                if (date_from or date_to) and precision not in {None, "day"}:
                    result["metadata"]["approximate_in_window"] = (
                        int(result["metadata"].get("approximate_in_window") or 0) + 1
                    )
                if (
                    review_quota_remaining is not None
                    and result["total_inserted"] >= review_quota_remaining
                ):
                    # Kuota habis: review baru dilewati, duplikat tetap diproses
                    # (gratis, dan tetap membawa perbaikan nama/tanggal/edit).
                    if review_exists is None or not review_exists(normalized):
                        quota_hit = True
                        result["metadata"]["skipped_quota"] = (
                            int(result["metadata"].get("skipped_quota") or 0) + 1
                        )
                        continue
                _, duplicate = insert_review(normalized)
                if duplicate:
                    result["total_duplicate"] += 1
                else:
                    result["total_inserted"] += 1
                if stored_times is not None:
                    stored_times.append((normalized["review_time"], precision))
            except Exception:
                result["total_failed"] += 1
                logger.exception("Failed to store one Apify review")
        return quota_hit

    def validate_target(self, target: object) -> int:
        try:
            value = int(target)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        maximum = self.settings.crawl_max_target_reviews
        if self.company_id is not None:
            quota = EntitlementService(
                self.company_id, self.session_factory
            ).review_quota()
            if quota > 0:
                maximum = min(maximum, quota)
        if not 1 <= value <= maximum:
            raise ValueError(f"Target review count must be between 1 and {maximum}.")
        return value

    def _resolve_actor_limit(
        self,
        crawl_target: CrawlTarget,
        *,
        target: int | None,
        coverage: str,
        budget: int | None,
        new_contract: bool,
    ) -> int:
        if coverage not in {"full_backfill", "date_window", "delta"}:
            raise ValueError(f"Unsupported coverage: {coverage}.")
        if coverage == "date_window":
            return self.settings.crawl_max_target_reviews
        requested = (
            budget or self.settings.crawl_max_target_reviews
            if coverage == "full_backfill"
            else budget
            or target
            or crawl_target.target_review_count
            or self.settings.crawl_default_review_limit
        )
        if not new_contract:
            return self.validate_target(requested)
        try:
            value = int(requested)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        if not 1 <= value <= self.settings.crawl_max_target_reviews:
            raise ValueError(
                "Target review count must be between 1 and "
                f"{self.settings.crawl_max_target_reviews}."
            )
        if self.company_id is None:
            return value
        return EntitlementService(
            self.company_id, self.session_factory
        ).clamp_review_target(value)

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
