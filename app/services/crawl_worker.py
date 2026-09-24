from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Competitor, CrawlBatch, CrawlJob, Location
from app.db.session import get_session_factory
from app.integrations.apify_token_pool import ApifyTokenPool
from app.services.apify_fetch_service import ApifyFetchService
from app.services.crawl_batch_view import serialize_batch
from app.services.crawl_result import stop_reason

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimedCrawlJob:
    id: int
    batch_id: int
    batch_public_id: str
    company_id: int
    location_id: int | None
    target_review_count: int
    date_from: datetime | None
    date_to: datetime | None
    attempts: int
    max_attempts: int
    competitor_id: int | None = None
    sort_by: str = "newest"
    crawl_mode: str = "regular_delta"
    max_reviews_to_collect: int | None = None
    scan_limit: int | None = None
    dry_run: bool = False
    coverage: str = "delta"
    budget: int | None = None
    review_quota_remaining: int | None = None
    source_run: dict | None = None


class CrawlWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        fetch_service_factory: Callable[[int], ApifyFetchService] | None = None,
    ):
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        if fetch_service_factory is not None:
            self.fetch_service_factory = fetch_service_factory
        else:
            token_pool = ApifyTokenPool(
                self.settings.apify_api_tokens,
                redis_url=self.settings.redis_url,
                exhausted_ttl_seconds=(
                    self.settings.apify_account_exhausted_ttl_seconds
                ),
                fallback_to_primary_on_exhaustion=True,
            )
            self.fetch_service_factory = lambda company_id: ApifyFetchService(
                company_id=company_id,
                session_factory=self.session_factory,
                settings=self.settings,
                token_pool=token_pool,
            )

    def _report_progress(
        self, job_id: int, fetched: int, scanned: int = 0
    ) -> None:
        """Simpan kemajuan sementara supaya status batch bisa membacanya.

        Ditulis ke result_json karena itu kolom yang memang sudah dibaca
        _serialize_batch. Nilainya ditimpa hasil akhir saat job selesai, jadi
        tidak ada dua sumber angka yang bisa berselisih.
        """
        try:
            with self.session_factory() as session:
                job = session.get(CrawlJob, job_id)
                if job is None or job.status != "running":
                    return
                current = dict(job.result_json or {})
                sama = (
                    int(current.get("progress_fetched") or 0) == int(fetched)
                    and int(current.get("progress_scanned") or 0) == int(scanned)
                )
                if sama:
                    return
                current["progress_fetched"] = int(fetched)
                # Berapa ulasan yang sudah DITELUSURI, termasuk yang dilewati
                # karena di luar rentang. Tanpa angka ini layar diam di nol
                # selama menembus ulasan yang lebih baru, dan tidak ada cara
                # membedakan sedang bekerja dari macet.
                current["progress_scanned"] = int(scanned)
                job.result_json = current
                session.commit()
        except Exception:  # kemajuan bersifat kosmetik, jangan sampai menggagalkan crawl
            logger.debug("gagal menyimpan kemajuan job %s", job_id, exc_info=True)

    def claim_next(self, *, worker_id: str) -> ClaimedCrawlJob | None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            due = or_(
                and_(
                    CrawlJob.status.in_(["queued", "retry_wait", "awaiting_source"]),
                    CrawlJob.available_at <= now,
                ),
                and_(
                    CrawlJob.status == "running",
                    CrawlJob.lease_expires_at.is_not(None),
                    CrawlJob.lease_expires_at <= now,
                ),
            )
            statement = (
                select(CrawlJob).where(due).order_by(CrawlJob.available_at, CrawlJob.id)
            )
            if session.bind.dialect.name in {"postgresql", "mysql"}:
                statement = statement.with_for_update(skip_locked=True)
            job = session.scalar(statement.limit(1))
            if job is None:
                return None
            batch = session.get(CrawlBatch, job.batch_id)
            # Handle run yang diparkir selalu dibawa, termasuk saat lease habis
            # karena worker mati di tengah pengecekan - membuangnya berarti
            # memulai run Apify kedua untuk cabang yang sama. _finish menulis
            # hasil baru tanpa handle, jadi retry tetap memulai run baru.
            source_run = (job.result_json or {}).get("source_run")
            # Mengecek run yang diparkir bukan percobaan baru.
            if job.status != "awaiting_source":
                job.attempts += 1
            job.status = "running"
            job.locked_by = worker_id
            job.locked_at = now
            job.lease_expires_at = now + timedelta(
                seconds=self.settings.crawl_worker_lease_seconds
            )
            job.started_at = job.started_at or now
            if batch is not None:
                batch.status = "running"
                batch.started_at = batch.started_at or now
            logger.info(
                "Worker %s claimed job %s (batch %s, location %s)",
                worker_id,
                job.id,
                batch.public_id if batch else "",
                job.location_id,
            )
            request_options = dict((job.result_json or {}).get("request") or {})
            crawl_mode = request_options.get("crawl_mode") or "regular_delta"
            quota_remaining = self._remaining_review_quota(
                session, job, request_options.get("review_quota_remaining")
            )
            session.commit()
            return ClaimedCrawlJob(
                id=job.id,
                batch_id=job.batch_id,
                batch_public_id=batch.public_id if batch else "",
                company_id=job.company_id,
                location_id=job.location_id,
                competitor_id=job.competitor_id,
                target_review_count=job.target_review_count,
                date_from=job.date_from,
                date_to=job.date_to,
                sort_by=job.sort_by or request_options.get("sort_by") or "newest",
                crawl_mode=crawl_mode,
                coverage=request_options.get("coverage")
                or {
                    "initial_backfill": "full_backfill",
                    "custom_range": "date_window",
                    "regular_delta": "delta",
                }.get(crawl_mode, "delta"),
                budget=request_options.get("budget"),
                review_quota_remaining=quota_remaining,
                source_run=source_run,
                max_reviews_to_collect=(
                    request_options.get("max_reviews_to_collect")
                    or job.target_review_count
                ),
                scan_limit=request_options.get("scan_limit"),
                dry_run=bool(request_options.get("dry_run", False)),
                attempts=job.attempts,
                max_attempts=job.max_attempts,
            )

    @staticmethod
    def _remaining_review_quota(
        session: Session, job: CrawlJob, batch_quota: object
    ) -> int | None:
        """Kuota OneBox untuk satu batch, dikurangi yang sudah dipakai job lain.

        ponytail: worker paralel bisa melampaui sebanyak satu job; pakai
        penghitung atomik per batch kalau itu penting.
        """
        if batch_quota is None:
            return None
        used = 0
        siblings = session.scalars(
            select(CrawlJob.result_json).where(
                CrawlJob.batch_id == job.batch_id,
                CrawlJob.id != job.id,
                CrawlJob.status.in_(["succeeded", "partial_success", "failed"]),
            )
        )
        for result_json in siblings:
            used += int((result_json or {}).get("total_inserted") or 0)
        return max(0, int(batch_quota) - used)

    def execute_next(self, *, worker_id: str) -> dict | None:
        claimed = self.claim_next(worker_id=worker_id)
        if claimed is None:
            return None
        try:
            if claimed.competitor_id is not None:
                return self._execute_competitor(claimed)
            with self.session_factory() as session:
                location = session.scalar(
                    select(Location).where(
                        Location.id == claimed.location_id,
                        Location.company_id == claimed.company_id,
                    )
                )
                eligible = bool(
                    location
                    and location.is_active
                    and location.crawl_enabled
                    and location.ingest_reviews
                )
            if not eligible:
                return self._finish(
                    claimed,
                    status="skipped",
                    result={
                        "reason": "target_disabled_or_removed",
                        "metadata": {"stop_reason": "target_disabled"},
                    },
                    error_code="TARGET_DISABLED",
                    error_message="Target is no longer eligible for crawling.",
                )

            fetch_service = self.fetch_service_factory(claimed.company_id)
            result = fetch_service.fetch_location(
                **self._parking_kwargs(fetch_service, claimed),
                location_id=claimed.location_id,
                target=claimed.max_reviews_to_collect or claimed.target_review_count,
                coverage=claimed.coverage,
                budget=claimed.budget,
                review_quota_remaining=claimed.review_quota_remaining,
                date_from=claimed.date_from,
                date_to=claimed.date_to,
                sort_by=claimed.sort_by or "newest",
                on_progress=lambda n, total, seen=0: self._report_progress(
                    claimed.id, n, seen
                ),
            )
            if "parked" in result:
                return self._park(claimed, result["parked"])
            if result.get("status") in {"success", "partial_success"}:
                if (
                    getattr(self.settings, "auto_analyze_on_crawl", True)
                    and claimed.location_id is not None
                ):
                    try:
                        from app.services.analysis_service import AnalysisService

                        analysis_service = AnalysisService(
                            company_id=claimed.company_id,
                            session_factory=self.session_factory,
                        )
                        analysis_res = analysis_service.analyze_pending(
                            location_id=claimed.location_id
                        )
                        logger.info(
                            "crawl_worker.auto_analysis_complete: location_id=%s, result=%s",
                            claimed.location_id,
                            analysis_res,
                        )
                    except Exception:
                        logger.exception(
                            "crawl_worker.auto_analysis_failed: location_id=%s",
                            claimed.location_id,
                        )
                status = (
                    "succeeded"
                    if result.get("status") == "success"
                    else "partial_success"
                )
                return self._finish(claimed, status=status, result=result)
            failure_metadata = result.get("metadata") or {}
            if self._is_permanent_source_failure(failure_metadata):
                return self._finish_permanent_source_failure(claimed, result)
            return self._retry_or_fail(
                claimed,
                error_code="CRAWL_FAILED",
                error_message=str(
                    result.get("error_message") or "Crawler returned a failed result."
                ),
                result=result,
            )
        except ValueError as exc:
            # Target di luar rentang, scan_limit tak masuk akal, target hilang:
            # itu galat permintaan/konfigurasi yang permanen. Meretry-nya 3x
            # sebagai WORKER_EXCEPTION hanya membuang ~6 menit per batch.
            logger.warning(
                "crawl_worker.invalid_request",
                extra={"job_id": claimed.id, "error": str(exc)},
            )
            return self._finish(
                claimed,
                status="failed",
                result={},
                error_code="INVALID_REQUEST",
                error_message=str(exc),
            )
        except Exception:
            logger.exception(
                "crawl_worker.execution_failed", extra={"job_id": claimed.id}
            )
            return self._retry_or_fail(
                claimed,
                error_code="WORKER_EXCEPTION",
                error_message="Crawler worker raised an unexpected exception.",
                result={},
            )

    def _execute_competitor(self, claimed: ClaimedCrawlJob) -> dict:
        """Jalankan job kompetitor.

        Kembarannya jalur cabang di execute_next, dengan dua beda yang
        disengaja: kelayakan diukur dari is_active saja (kompetitor tidak punya
        cermin Location untuk diperiksa), dan hasilnya mendarat di
        competitor_reviews sehingga tidak ikut mengalir ke tiket OneBox.
        """
        with self.session_factory() as session:
            competitor = session.scalar(
                select(Competitor).where(
                    Competitor.id == claimed.competitor_id,
                    Competitor.company_id == claimed.company_id,
                )
            )
            eligible = bool(competitor and competitor.is_active)
        if not eligible:
            return self._finish(
                claimed,
                status="skipped",
                result={
                    "reason": "target_disabled_or_removed",
                    "metadata": {"stop_reason": "target_disabled"},
                },
                error_code="TARGET_DISABLED",
                error_message="Target is no longer eligible for crawling.",
            )

        fetch_service = self.fetch_service_factory(claimed.company_id)
        result = fetch_service.fetch_competitor(
            **self._parking_kwargs(fetch_service, claimed),
            competitor_id=claimed.competitor_id,
            target=claimed.max_reviews_to_collect or claimed.target_review_count,
            coverage=claimed.coverage,
            budget=claimed.budget,
            review_quota_remaining=claimed.review_quota_remaining,
            date_from=claimed.date_from,
            date_to=claimed.date_to,
            sort_by=claimed.sort_by or "newest",
            on_progress=lambda n, total, seen=0: self._report_progress(
                claimed.id, n, seen
            ),
        )
        if "parked" in result:
            return self._park(claimed, result["parked"])
        if result.get("status") in {"success", "partial_success"}:
            return self._finish(claimed, status="succeeded", result=result)
        failure_metadata = result.get("metadata") or {}
        if self._is_permanent_source_failure(failure_metadata):
            return self._finish_permanent_source_failure(claimed, result)
        return self._retry_or_fail(
            claimed,
            error_code="CRAWL_FAILED",
            error_message=str(
                result.get("error_message") or "Crawler returned a failed result."
            ),
            result=result,
        )

    def _parking_kwargs(self, fetch_service, claimed: ClaimedCrawlJob) -> dict:
        if not (
            self.settings.crawl_async_source_runs
            and getattr(fetch_service, "supports_parking", False)
        ):
            return {}
        return {"park": True, "source_run": claimed.source_run}

    def _park(self, claimed: ClaimedCrawlJob, source_run: dict) -> dict:
        """Lepas worker; run Apify tetap jalan dan dicek lagi nanti (CS-3)."""
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            job = session.get(CrawlJob, claimed.id)
            if job is None:
                raise RuntimeError("Claimed crawl job disappeared.")
            current = dict(job.result_json or {})
            current["source_run"] = source_run
            metadata = dict(current.get("metadata") or {})
            metadata.pop("stop_reason", None)
            metadata.pop("stopped_reason", None)
            current["metadata"] = metadata
            job.result_json = current
            job.status = "awaiting_source"
            job.available_at = now + timedelta(
                seconds=self.settings.crawl_source_poll_seconds
            )
            job.locked_by = None
            job.locked_at = None
            job.lease_expires_at = None
            session.commit()
            batch = session.get(CrawlBatch, claimed.batch_id)
            return serialize_batch(session, batch)

    def _retry_or_fail(
        self,
        claimed: ClaimedCrawlJob,
        *,
        error_code: str,
        error_message: str,
        result: dict,
    ) -> dict:
        if claimed.attempts < claimed.max_attempts:
            delay = self.settings.crawl_worker_retry_base_seconds * (
                5 ** (claimed.attempts - 1)
            )
            return self._finish(
                claimed,
                status="retry_wait",
                result=result,
                error_code=error_code,
                error_message=error_message,
                available_at=datetime.now(timezone.utc) + timedelta(seconds=delay),
            )
        return self._finish(
            claimed,
            status="failed",
            result=result,
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    def _is_permanent_source_failure(metadata: dict) -> bool:
        # Existing ReviewSourceError instances did not carry a code and were
        # historically retried. Requiring an explicit code preserves that
        # behavior while allowing known operator-action failures to fail fast.
        return bool(
            metadata.get("failure_code")
            and metadata.get("retriable") is False
        )

    def _finish_permanent_source_failure(
        self, claimed: ClaimedCrawlJob, result: dict
    ) -> dict:
        metadata = result.get("metadata") or {}
        return self._finish(
            claimed,
            status="failed",
            result=result,
            error_code=str(metadata["failure_code"]),
            error_message=str(
                result.get("error_message")
                or "Crawler returned a permanent failure."
            ),
        )

    def _finish(
        self,
        claimed: ClaimedCrawlJob,
        *,
        status: str,
        result: dict,
        error_code: str | None = None,
        error_message: str | None = None,
        available_at: datetime | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            job = session.get(CrawlJob, claimed.id)
            if job is None:
                raise RuntimeError("Claimed crawl job disappeared.")
            previous_request = dict((job.result_json or {}).get("request") or {})
            job.status = status
            enriched_result = dict(result or {})
            if previous_request:
                enriched_result["request"] = previous_request
                metadata = dict(enriched_result.get("metadata") or {})
                metadata.setdefault("crawl_mode", previous_request.get("crawl_mode"))
                metadata.setdefault("coverage", previous_request.get("coverage"))
                metadata.setdefault("budget", previous_request.get("budget"))
                metadata.setdefault(
                    "max_reviews_to_collect",
                    previous_request.get("max_reviews_to_collect"),
                )
                metadata.setdefault("scan_limit", previous_request.get("scan_limit"))
                enriched_result["metadata"] = metadata
            metadata = dict(enriched_result.get("metadata") or {})
            public_stop_reason = stop_reason(enriched_result)
            if public_stop_reason:
                metadata["stop_reason"] = public_stop_reason
                enriched_result["metadata"] = metadata
            job.result_json = enriched_result
            job.last_error_code = error_code
            job.last_error = (error_message or "")[:2000] or None
            job.available_at = available_at or job.available_at
            job.locked_by = None
            job.locked_at = None
            job.lease_expires_at = None
            if status in {"succeeded", "partial_success", "skipped", "failed"}:
                job.finished_at = now
            logger.info(
                "Job %s finished: status=%s, fetched=%s, inserted=%s, duplicate=%s, stop_reason=%s",
                claimed.id,
                status,
                enriched_result.get("total_fetched", 0),
                enriched_result.get("total_inserted", 0),
                enriched_result.get("total_duplicate", 0),
                public_stop_reason,
            )
            session.flush()
            batch = session.get(CrawlBatch, claimed.batch_id)
            if batch is None:
                raise RuntimeError("Crawl batch disappeared.")
            self._refresh_batch_status(session, batch, now)
            session.commit()
            session.refresh(batch)
            return serialize_batch(session, batch)

    @staticmethod
    def _refresh_batch_status(
        session: Session, batch: CrawlBatch, now: datetime
    ) -> None:
        statuses = list(
            session.scalars(
                select(CrawlJob.status).where(CrawlJob.batch_id == batch.id)
            )
        )
        terminal = {"succeeded", "partial_success", "skipped", "failed"}
        if any(status not in terminal for status in statuses):
            batch.status = "running"
            return
        failed = statuses.count("failed")
        if failed == len(statuses):
            batch.status = "failed"
        elif failed:
            batch.status = "partial_failed"
        else:
            batch.status = "completed"
        batch.finished_at = now
