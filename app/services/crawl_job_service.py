from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Competitor, CrawlBatch, CrawlJob, Location
from app.db.session import get_session_factory
from app.services.crawl_result import (
    CrawlRequestSnapshot,
    matched_count,
    rating_snapshot,
    scanned_count,
    stop_reason,
)
from app.services.selenium_fetch_service import SeleniumFetchService

logger = logging.getLogger(__name__)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _batch_kind(jobs) -> str:
    """location | competitor | mixed.

    Batch kosong dianggap location: itu bentuk lama, dan menyebutnya apa pun
    selain itu akan membuat batch lawas berpindah layar.
    """
    jenis = {
        "competitor" if job.competitor_id is not None else "location"
        for job in jobs
    }
    if len(jenis) == 1:
        return jenis.pop()
    return "mixed" if jenis else "location"


class CrawlQueueError(ValueError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


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


class CrawlJobService:
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

    @staticmethod
    def request_fingerprint(
        slot: str | None,
        onebox_location_ids: list[int],
        target_review_counts: dict[int, int] | None = None,
        target_date_ranges: dict | None = None,
        target_sorts: dict | None = None,
        target_crawl_options: dict | None = None,
        competitor_targets: dict | None = None,
    ) -> str:
        payload: dict = {
            "slot": slot,
            "onebox_location_ids": sorted(onebox_location_ids),
        }
        if competitor_targets:
            # Alasannya sama seperti cabang: idempotency key yang sama dengan
            # daftar kompetitor berbeda adalah permintaan berbeda, bukan
            # pengulangan. Tanpa ini permintaan kedua akan diam-diam
            # mengembalikan batch pertama.
            payload["competitor_targets"] = {
                place_id: {
                    "target_review_count": competitor_targets[place_id].get(
                        "target_review_count"
                    ),
                    "date_from": _iso(
                        competitor_targets[place_id].get("date_from")
                    ),
                    "date_to": _iso(competitor_targets[place_id].get("date_to")),
                    "sort_by": competitor_targets[place_id].get("sort_by")
                    or "newest",
                }
                for place_id in sorted(competitor_targets)
            }
        if target_sorts:
            # Urutan ikut sidik jari: permintaan yang sama dengan urutan berbeda
            # akan menghasilkan kumpulan ulasan yang berbeda pula, jadi bukan
            # pengulangan.
            payload["target_sorts"] = {
                str(k): v for k, v in sorted(target_sorts.items())
            }
        if target_crawl_options:
            payload["target_crawl_options"] = {
                str(k): {
                    option_key: _iso(option_value)
                    for option_key, option_value in sorted(options.items())
                    if option_value is not None
                }
                for k, options in sorted(target_crawl_options.items())
            }
        if target_date_ranges:
            # Rentang ikut sidik jari: idempotency key yang sama dengan rentang
            # berbeda adalah permintaan berbeda, bukan pengulangan.
            payload["target_date_ranges"] = {
                str(location_id): [
                    d.isoformat() if d else None
                    for d in target_date_ranges[location_id]
                ]
                for location_id in sorted(target_date_ranges)
            }
        if target_review_counts:
            payload["target_review_counts"] = {
                str(location_id): target_review_counts[location_id]
                for location_id in sorted(target_review_counts)
            }
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def enqueue(
        self,
        *,
        company_id: int,
        client_id: int,
        idempotency_key: str,
        onebox_location_ids: list[int],
        slot: str | None,
        target_review_counts: dict[int, int] | None = None,
        target_date_ranges: dict | None = None,
        target_sorts: dict | None = None,
        target_crawl_options: dict | None = None,
        competitor_targets: list[dict] | None = None,
    ) -> tuple[dict, bool]:
        key = idempotency_key.strip()
        if not 8 <= len(key) <= 128:
            raise CrawlQueueError(
                400,
                "INVALID_IDEMPOTENCY_KEY",
                "Idempotency-Key must contain between 8 and 128 characters.",
            )
        target_ids = sorted(set(onebox_location_ids))
        competitor_specs: dict[str, dict] = {}
        for spec in competitor_targets or []:
            place_id = str(spec.get("external_place_id") or "").strip()
            if place_id:
                competitor_specs[place_id] = spec
        if not target_ids and not competitor_specs:
            raise CrawlQueueError(
                400,
                "INVALID_TARGETS",
                "At least one crawl target is required.",
            )
        target_review_counts = target_review_counts or {}
        unknown_overrides = sorted(set(target_review_counts) - set(target_ids))
        if unknown_overrides:
            raise CrawlQueueError(
                400,
                "INVALID_TARGETS",
                "Target review count override references an unknown location target.",
            )
        target_date_ranges = target_date_ranges or {}
        target_sorts = target_sorts or {}
        target_crawl_options = target_crawl_options or {}
        fingerprint = self.request_fingerprint(
            slot, target_ids, target_review_counts, target_date_ranges,
            target_sorts, target_crawl_options, competitor_specs,
        )

        with self.session_factory() as session:
            existing = session.scalar(
                select(CrawlBatch).where(
                    CrawlBatch.company_id == company_id,
                    CrawlBatch.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise CrawlQueueError(
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key was already used with a different payload.",
                    )
                return self._serialize_batch(session, existing), False

            locations = list(
                session.scalars(
                    select(Location)
                    .where(
                        Location.company_id == company_id,
                        Location.onebox_location_id.in_(target_ids),
                        Location.is_active.is_(True),
                        Location.crawl_enabled.is_(True),
                        Location.ingest_reviews.is_(True),
                    )
                    .order_by(Location.id)
                )
            )
            found_ids = {location.onebox_location_id for location in locations}
            missing = [target for target in target_ids if target not in found_ids]

            if missing:
                # Cabang bisa saja baru dibuat di OneBox dan belum tercermin di
                # cache lokal. OneBox pemilik daftarnya, jadi tanya ulang ke
                # sana sekali sebelum menyerah — bukan menyuruh orang
                # menjalankan refresh manual di mesin ini.
                if self._refresh_worklist_once(company_id, missing):
                    locations = list(
                        session.scalars(
                            select(Location)
                            .where(
                                Location.company_id == company_id,
                                Location.onebox_location_id.in_(target_ids),
                                Location.is_active.is_(True),
                                Location.crawl_enabled.is_(True),
                                Location.ingest_reviews.is_(True),
                            )
                            .order_by(Location.id)
                        )
                    )
                    found_ids = {location.onebox_location_id for location in locations}
                    missing = [target for target in target_ids if target not in found_ids]

            if missing:
                raise CrawlQueueError(
                    404,
                    "TARGET_NOT_FOUND",
                    "One or more crawl targets are absent, disabled, or outside this tenant.",
                )

            # Kompetitor di-resolve lewat external_place_id miliknya sendiri,
            # bukan lewat tabel locations. Syarat ingest_reviews sengaja tidak
            # dipakai di sini: bendera itu menandai "boleh jadi tiket OneBox",
            # dan ulasan kompetitor memang tidak boleh — tapi tetap harus bisa
            # ditarik sebagai pembanding.
            competitors = []
            if competitor_specs:
                competitors = list(
                    session.scalars(
                        select(Competitor)
                        .where(
                            Competitor.company_id == company_id,
                            Competitor.external_place_id.in_(
                                sorted(competitor_specs)
                            ),
                            Competitor.is_active.is_(True),
                        )
                        .order_by(Competitor.id)
                    )
                )
                found_places = {
                    competitor.external_place_id for competitor in competitors
                }
                missing_places = [
                    place
                    for place in sorted(competitor_specs)
                    if place not in found_places
                ]
                if missing_places:
                    raise CrawlQueueError(
                        404,
                        "TARGET_NOT_FOUND",
                        "One or more competitor targets are absent, disabled, "
                        "or outside this tenant.",
                    )

            active_batch = self._find_active_batch_for_single_target(
                session=session,
                company_id=company_id,
                locations=locations,
                competitors=competitors,
                target_date_ranges=target_date_ranges,
                competitor_specs=competitor_specs,
            )
            if active_batch is not None:
                return self._serialize_batch(session, active_batch), False

            batch = CrawlBatch(
                public_id=str(uuid4()),
                company_id=company_id,
                requested_by_client_id=client_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                slot=(slot or "").strip() or None,
                status="queued",
                analyze_after_crawl=False,
            )
            session.add(batch)
            session.flush()
            for location in locations:
                options = dict(
                    target_crawl_options.get(location.onebox_location_id) or {}
                )
                target_count = target_review_counts.get(
                    location.onebox_location_id,
                    location.target_review_count,
                )
                date_from, date_to = target_date_ranges.get(
                    location.onebox_location_id, (None, None)
                )
                crawl_mode = self._normalize_crawl_mode(
                    options.get("crawl_mode"), date_from, date_to
                )
                scan_limit = self._normalize_scan_limit(
                    options.get("scan_limit"), target_count, crawl_mode
                )
                session.add(
                    CrawlJob(
                        batch_id=batch.id,
                        company_id=company_id,
                        location_id=location.id,
                        onebox_location_id=location.onebox_location_id,
                        status="queued",
                        source_snapshot=location.source,
                        date_from=date_from,
                        date_to=date_to,
                        sort_by=target_sorts.get(
                            location.onebox_location_id, "newest"
                        ),
                        target_review_count=target_count,
                        result_json=self._initial_job_result(
                            crawl_mode=crawl_mode,
                            max_reviews_to_collect=target_count,
                            scan_limit=scan_limit,
                            dry_run=bool(options.get("dry_run", False)),
                            date_from=date_from,
                            date_to=date_to,
                            sort_by=target_sorts.get(
                                location.onebox_location_id, "newest"
                            ),
                        ),
                        max_attempts=self.settings.crawl_worker_max_attempts,
                    )
                )
            for competitor in competitors:
                spec = competitor_specs[competitor.external_place_id]
                target_count = (
                    spec.get("target_review_count")
                    or competitor.target_review_count
                )
                date_from = spec.get("date_from")
                date_to = spec.get("date_to")
                crawl_mode = self._normalize_crawl_mode(
                    spec.get("crawl_mode"), date_from, date_to
                )
                scan_limit = self._normalize_scan_limit(
                    spec.get("scan_limit"), target_count, crawl_mode
                )
                session.add(
                    CrawlJob(
                        batch_id=batch.id,
                        company_id=company_id,
                        location_id=None,
                        onebox_location_id=None,
                        competitor_id=competitor.id,
                        status="queued",
                        source_snapshot=competitor.source,
                        date_from=date_from,
                        date_to=date_to,
                        sort_by=spec.get("sort_by") or "newest",
                        target_review_count=target_count,
                        result_json=self._initial_job_result(
                            crawl_mode=crawl_mode,
                            max_reviews_to_collect=target_count,
                            scan_limit=scan_limit,
                            dry_run=bool(spec.get("dry_run", False)),
                            date_from=date_from,
                            date_to=date_to,
                            sort_by=spec.get("sort_by") or "newest",
                        ),
                        max_attempts=self.settings.crawl_worker_max_attempts,
                    )
                )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(CrawlBatch).where(
                        CrawlBatch.company_id == company_id,
                        CrawlBatch.idempotency_key == key,
                    )
                )
                if existing is None or existing.request_fingerprint != fingerprint:
                    raise
                return self._serialize_batch(session, existing), False
            session.refresh(batch)
            logger.info(
                "crawl_queue.enqueued",
                extra={
                    "batch_id": batch.public_id,
                    "company_id": company_id,
                    "job_count": len(locations) + len(competitors),
                },
            )
            return self._serialize_batch(session, batch), True

    @staticmethod
    def _normalize_crawl_mode(
        crawl_mode: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> str:
        if crawl_mode in {"initial_backfill", "regular_delta", "custom_range"}:
            return crawl_mode
        if date_from is not None or date_to is not None:
            return "custom_range"
        return "regular_delta"

    @staticmethod
    def _normalize_scan_limit(
        scan_limit: object,
        max_reviews_to_collect: int,
        crawl_mode: str,
    ) -> int:
        default_multiplier = 5 if crawl_mode == "custom_range" else 1
        if crawl_mode == "initial_backfill":
            default_multiplier = 10
        default_limit = max(max_reviews_to_collect, max_reviews_to_collect * default_multiplier)
        try:
            value = int(scan_limit) if scan_limit is not None else default_limit
        except (TypeError, ValueError):
            value = default_limit
        return max(max_reviews_to_collect, min(value, 5000))

    @staticmethod
    def _initial_job_result(
        *,
        crawl_mode: str,
        max_reviews_to_collect: int,
        scan_limit: int,
        dry_run: bool,
        date_from: datetime | None,
        date_to: datetime | None,
        sort_by: str,
    ) -> dict:
        request: CrawlRequestSnapshot = {
            "crawl_mode": crawl_mode,
            "max_reviews_to_collect": max_reviews_to_collect,
            "scan_limit": scan_limit,
            "dry_run": dry_run,
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "sort_by": sort_by or "newest",
        }
        return {"request": request}

    @staticmethod
    def _datetime_filter(column, value: datetime | None):
        return column.is_(None) if value is None else column == value

    def _find_active_batch_for_single_target(
        self,
        *,
        session: Session,
        company_id: int,
        locations: list[Location],
        competitors: list[Competitor],
        target_date_ranges: dict,
        competitor_specs: dict,
    ) -> CrawlBatch | None:
        if len(locations) + len(competitors) != 1:
            return None
        active_statuses = {"queued", "running", "retry_wait"}
        conditions = [
            CrawlJob.company_id == company_id,
            CrawlJob.status.in_(active_statuses),
        ]
        if locations:
            location = locations[0]
            date_from, date_to = target_date_ranges.get(
                location.onebox_location_id, (None, None)
            )
            conditions.extend(
                [
                    CrawlJob.location_id == location.id,
                    CrawlJob.competitor_id.is_(None),
                    self._datetime_filter(CrawlJob.date_from, date_from),
                    self._datetime_filter(CrawlJob.date_to, date_to),
                ]
            )
        else:
            competitor = competitors[0]
            spec = competitor_specs[competitor.external_place_id]
            conditions.extend(
                [
                    CrawlJob.competitor_id == competitor.id,
                    CrawlJob.location_id.is_(None),
                    self._datetime_filter(CrawlJob.date_from, spec.get("date_from")),
                    self._datetime_filter(CrawlJob.date_to, spec.get("date_to")),
                ]
            )
        active_job = session.scalar(
            select(CrawlJob).where(*conditions).order_by(CrawlJob.id.desc()).limit(1)
        )
        if active_job is None:
            return None
        return session.get(CrawlBatch, active_job.batch_id)

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

    def _refresh_worklist_once(self, company_id: int, missing: list[int]) -> bool:
        """Tarik ulang worklist OneBox. True kalau ada yang berubah/terisi.

        Sengaja tidak melempar: gagal menyegarkan tidak boleh mengubah bentuk
        kegagalan yang dilihat pemanggil. Kalau refresh gagal, target tetap
        dianggap tidak dikenal dan TARGET_NOT_FOUND yang keluar — sama seperti
        sebelumnya, hanya dengan satu usaha tambahan yang tidak merugikan.
        """
        from app.services.worklist_sync_service import (
            WorklistSyncError,
            WorklistSyncService,
        )

        if not WorklistSyncService.is_configured(self.settings):
            logger.warning(
                "crawl target %s tidak dikenal dan worklist OneBox belum "
                "dikonfigurasi (ONEBOX_BASE_URL/SVC_EMAIL/SVC_PASSWORD/SITE_ID)",
                missing,
            )
            return False

        try:
            result = WorklistSyncService(
                company_id=company_id, session_factory=self.session_factory
            ).refresh()
        except WorklistSyncError as exc:
            logger.warning("refresh worklist otomatis gagal untuk %s: %s", missing, exc)
            return False
        except Exception:  # pragma: no cover - jaring pengaman
            logger.exception("refresh worklist otomatis gagal untuk %s", missing)
            return False

        logger.info(
            "worklist disegarkan otomatis karena target %s belum dikenal "
            "(fetched=%s upserted=%s)",
            missing,
            getattr(result, "fetched", None),
            getattr(result, "upserted", None),
        )
        return True

    def get_batch(self, *, company_id: int, public_id: str) -> dict:
        with self.session_factory() as session:
            batch = session.scalar(
                select(CrawlBatch).where(
                    CrawlBatch.public_id == public_id,
                    CrawlBatch.company_id == company_id,
                )
            )
            if batch is None:
                raise CrawlQueueError(
                    404, "BATCH_NOT_FOUND", "Crawl batch was not found."
                )
            return self._serialize_batch(session, batch)

    def list_batches(self, *, company_id: int, limit: int = 20) -> list[dict]:
        with self.session_factory() as session:
            batches = list(
                session.scalars(
                    select(CrawlBatch)
                    .where(CrawlBatch.company_id == company_id)
                    .order_by(CrawlBatch.id.desc())
                    .limit(max(1, min(limit, 100)))
                )
            )
            return [
                self._serialize_batch(session, batch, include_jobs=False)
                for batch in batches
            ]

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
            return self._serialize_batch(session, batch)

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

    @staticmethod
    def _serialize_batch(
        session: Session, batch: CrawlBatch, include_jobs: bool = True
    ) -> dict:
        jobs = list(
            session.scalars(
                select(CrawlJob)
                .where(CrawlJob.batch_id == batch.id)
                .order_by(CrawlJob.id)
            )
        )
        counts = {
            status: 0
            for status in (
                "queued",
                "running",
                "retry_wait",
                "succeeded",
                "partial_success",
                "skipped",
                "failed",
            )
        }
        review_counts = {
            "target": 0,
            "scanned": 0,
            "fetched": 0,
            "matched": 0,
            "out_of_range": 0,
            "out_of_range_newer": 0,
            "out_of_range_older": 0,
            "inserted": 0,
            "duplicate": 0,
            "failed": 0,
        }
        for job in jobs:
            counts[job.status] = counts.get(job.status, 0) + 1
            review_counts["target"] += job.target_review_count
            result = job.result_json or {}
            # Job yang masih berjalan belum punya total_fetched; yang ada baru
            # progress_fetched dari loop gulir. Dipakai supaya layar bisa
            # menampilkan "n dari target" selagi crawl berlangsung.
            review_counts["fetched"] += int(
                result.get("total_fetched") or result.get("progress_fetched") or 0
            )
            metadata = result.get("metadata") or {}
            out_of_range_count = int(result.get("total_skipped_out_of_range") or 0)
            review_counts["scanned"] += scanned_count(result)
            review_counts["matched"] += matched_count(result)
            review_counts["out_of_range"] += out_of_range_count
            review_counts["out_of_range_newer"] += int(
                metadata.get("out_of_range_newer") or 0
            )
            review_counts["out_of_range_older"] += int(
                metadata.get("out_of_range_older") or 0
            )
            review_counts["inserted"] += int(result.get("total_inserted") or 0)
            review_counts["duplicate"] += int(result.get("total_duplicate") or 0)
            review_counts["failed"] += int(result.get("total_failed") or 0)
        batch_stop_reason, stop_reasons = CrawlJobService._batch_stop_reasons(jobs)
        limits = {
            "max_reviews_to_collect": review_counts["target"],
            "scan_limit": sum(
                int(((job.result_json or {}).get("request") or {}).get("scan_limit") or 0)
                for job in jobs
            ),
        }
        data = {
            "batch_id": batch.public_id,
            "status": batch.status,
            "slot": batch.slot,
            "job_count": len(jobs),
            "counts": counts,
            "review_counts": review_counts,
            "created_at": batch.created_at,
            "started_at": batch.started_at,
            "finished_at": batch.finished_at,
            "stop_reason": batch_stop_reason,
            "stop_reasons": stop_reasons,
            # Jobs sudah dimuat di atas, jadi ini tidak menambah query.
            # Disertakan juga saat include_jobs False: daftar batch tanpa
            # penyebut cabang memaksa OneBox memanggil detail tiap batch.
            "targets": [
                job.onebox_location_id
                for job in jobs
                if job.onebox_location_id is not None
            ],
            # Jenis batch, supaya daftar riwayat bisa dipisah tanpa memanggil
            # detail tiap batch. Tanpa ini pemanggil hanya bisa menebak dari
            # targets yang kosong, dan batch cabang yang gagal total akan
            # tertukar dengan batch kompetitor.
            "kind": _batch_kind(jobs),
            "competitors": [
                job.competitor_id for job in jobs if job.competitor_id is not None
            ],
            "reused_existing_job": False,
            "limits": limits,
        }
        if include_jobs:
            data["jobs"] = [
                {
                    "job_id": job.id,
                    "onebox_location_id": job.onebox_location_id,
                    "competitor_id": job.competitor_id,
                    "kind": (
                        "competitor"
                        if job.competitor_id is not None
                        else "location"
                    ),
                    "target_review_count": job.target_review_count,
                    "max_reviews_to_collect": (
                        ((job.result_json or {}).get("request") or {}).get(
                            "max_reviews_to_collect"
                        )
                        or job.target_review_count
                    ),
                    "scan_limit": ((job.result_json or {}).get("request") or {}).get(
                        "scan_limit"
                    ),
                    "crawl_mode": ((job.result_json or {}).get("request") or {}).get(
                        "crawl_mode"
                    ),
                    "stop_reason": stop_reason(job.result_json or {}),
                    "rating_snapshot": rating_snapshot(job.result_json or {}),
                    "status": job.status,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "result": job.result_json,
                    "error": (
                        {"code": job.last_error_code, "message": job.last_error}
                        if job.last_error_code
                        else None
                    ),
                    "started_at": job.started_at,
                    "finished_at": job.finished_at,
                }
                for job in jobs
            ]
        return data

    @staticmethod
    def _batch_stop_reasons(jobs) -> tuple[str | None, dict[str, int]]:
        counts: dict[str, int] = {}
        for job in jobs:
            reason = stop_reason(job.result_json or {})
            if not reason:
                continue
            counts[reason] = counts.get(reason, 0) + 1
        if not counts:
            return None, {}
        if len(counts) == 1:
            return next(iter(counts)), counts
        return "mixed", counts
