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
from app.services.crawl_batch_view import serialize_batch
from app.services.crawl_result import stop_reason
from app.services.selenium_fetch_service import SeleniumFetchService

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


class CrawlWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        fetch_service_factory: Callable[[int], SeleniumFetchService] | None = None,
    ):
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        self.fetch_service_factory = fetch_service_factory or (
            lambda company_id: SeleniumFetchService(
                company_id=company_id,
                session_factory=self.session_factory,
                settings=self.settings,
            )
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
                    CrawlJob.status.in_(["queued", "retry_wait"]),
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
            job.status = "running"
            job.attempts += 1
            job.locked_by = worker_id
            job.locked_at = now
            job.lease_expires_at = now + timedelta(
                seconds=self.settings.crawl_worker_lease_seconds
            )
            job.started_at = job.started_at or now
            if batch is not None:
                batch.status = "running"
                batch.started_at = batch.started_at or now
            request_options = dict((job.result_json or {}).get("request") or {})
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
                crawl_mode=request_options.get("crawl_mode") or "regular_delta",
                max_reviews_to_collect=(
                    request_options.get("max_reviews_to_collect")
                    or job.target_review_count
                ),
                scan_limit=request_options.get("scan_limit"),
                dry_run=bool(request_options.get("dry_run", False)),
                attempts=job.attempts,
                max_attempts=job.max_attempts,
            )

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
                    result={"reason": "target_disabled_or_removed"},
                    error_code="TARGET_DISABLED",
                    error_message="Target is no longer eligible for crawling.",
                )

            fetch_service = self.fetch_service_factory(claimed.company_id)
            result = fetch_service.fetch_location(
                claimed.location_id,
                target=claimed.max_reviews_to_collect or claimed.target_review_count,
                date_from=claimed.date_from,
                date_to=claimed.date_to,
                sort_by=claimed.sort_by or "newest",
                scan_limit=claimed.scan_limit,
                # Batas waktu per job. Tanpa ini satu permintaan rentang jauh
                # ke belakang bisa menahan worker sampai batas gulir habis,
                # sementara cabang lain mengantre.
                time_limit_seconds=600,
                on_progress=lambda n, total, seen=0: self._report_progress(
                    claimed.id, n, seen
                ),
            )
            if result.get("status") == "success":
                return self._finish(claimed, status="succeeded", result=result)
            if result.get("status") == "partial_success":
                return self._finish(claimed, status="partial_success", result=result)
            return self._retry_or_fail(
                claimed,
                error_code="CRAWL_FAILED",
                error_message=str(
                    result.get("error_message") or "Crawler returned a failed result."
                ),
                result=result,
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
                result={"reason": "target_disabled_or_removed"},
                error_code="TARGET_DISABLED",
                error_message="Target is no longer eligible for crawling.",
            )

        fetch_service = self.fetch_service_factory(claimed.company_id)
        result = fetch_service.fetch_competitor(
            claimed.competitor_id,
            target=claimed.max_reviews_to_collect or claimed.target_review_count,
            date_from=claimed.date_from,
            date_to=claimed.date_to,
            sort_by=claimed.sort_by or "newest",
            scan_limit=claimed.scan_limit,
            time_limit_seconds=600,
            on_progress=lambda n, total, seen=0: self._report_progress(
                claimed.id, n, seen
            ),
        )
        if result.get("status") in {"success", "partial_success"}:
            return self._finish(claimed, status="succeeded", result=result)
        return self._retry_or_fail(
            claimed,
            error_code="CRAWL_FAILED",
            error_message=str(
                result.get("error_message") or "Crawler returned a failed result."
            ),
            result=result,
        )

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

