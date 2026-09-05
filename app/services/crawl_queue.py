from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Competitor, CrawlBatch, CrawlJob, Location
from app.db.session import get_session_factory
from app.services.crawl_batch_view import serialize_batch
from app.services.crawl_result import CrawlRequestSnapshot

logger = logging.getLogger(__name__)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


class CrawlQueueError(ValueError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class CrawlQueue:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
    ):
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()

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
                return serialize_batch(session, existing), False

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
                return serialize_batch(session, active_batch), False

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
                return serialize_batch(session, existing), False
            session.refresh(batch)
            logger.info(
                "crawl_queue.enqueued",
                extra={
                    "batch_id": batch.public_id,
                    "company_id": company_id,
                    "job_count": len(locations) + len(competitors),
                },
            )
            return serialize_batch(session, batch), True

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
            return serialize_batch(session, batch)

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
                serialize_batch(session, batch, include_jobs=False)
                for batch in batches
            ]

