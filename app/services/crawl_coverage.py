from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Competitor, CrawlWindowLog, Location
from app.services.crawl_target import CrawlTarget

COVERAGE_FIELDS = (
    "newest_crawled_at",
    "newest_crawled_precision",
    "oldest_crawled_at",
    "backfill_completed_at",
    "last_successful_crawl_at",
    "last_expected_review_count",
)
SWEEP_EVERY = timedelta(days=7)


def as_utc(value: datetime | None) -> datetime | None:
    # SQLite mengembalikan datetime naif; semua kolom ini disimpan UTC.
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


class CrawlCoverageStore:
    """Cakupan crawl per target (spec §4.5): kursor yang dipegang Crawler."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _model(crawl_target):
        if isinstance(crawl_target, Location) or getattr(crawl_target, "kind", None) == "location":
            return Location
        return Competitor

    def load(self, crawl_target: CrawlTarget) -> dict | None:
        with self.session_factory() as session:
            row = session.get(self._model(crawl_target), crawl_target.id)
            return self.serialize(row)

    @staticmethod
    def serialize(row) -> dict | None:
        if row is None:
            return None
        return {
            field: _iso(
                as_utc(getattr(row, field))
                if isinstance(getattr(row, field), datetime)
                else getattr(row, field)
            )
            for field in COVERAGE_FIELDS
        }

    def delta_lower_bound(
        self,
        crawl_target: CrawlTarget,
        requested_from: datetime | None,
        *,
        margin: timedelta,
        sweep_margin: timedelta,
        now: datetime,
    ) -> tuple[datetime | None, bool]:
        """Batas bawah delta dan apakah run ini sekaligus safety sweep (F3).

        Batas dari OneBox hanya dipakai bila lebih baru daripada kursor
        Crawler - kursor OneBox yang tertinggal tidak boleh memicu crawl ulang.
        """
        with self.session_factory() as session:
            row = session.get(self._model(crawl_target), crawl_target.id)
            newest = as_utc(row.newest_crawled_at) if row is not None else None
            last_sweep = as_utc(row.last_sweep_at) if row is not None else None
        if newest is None:
            return as_utc(requested_from), False
        sweep = last_sweep is None or now - last_sweep >= SWEEP_EVERY
        own_bound = newest - (sweep_margin if sweep else margin)
        requested = as_utc(requested_from)
        if requested is not None and not sweep and requested > own_bound:
            return requested, False
        return own_bound, sweep

    def record_success(
        self,
        crawl_target: CrawlTarget,
        *,
        coverage: str,
        stored_times: list[tuple[datetime, str | None]],
        expected_review_count: int | None,
        complete: bool,
        swept: bool,
        now: datetime,
    ) -> dict | None:
        with self.session_factory() as session:
            row = session.get(self._model(crawl_target), crawl_target.id)
            if row is None:
                return None
            times = [(as_utc(t), p) for t, p in stored_times if t is not None]
            if times:
                newest_time, newest_precision = max(times, key=lambda item: item[0])
                oldest_time = min(item[0] for item in times)
                current_newest = as_utc(row.newest_crawled_at)
                # date_window tidak pernah memajukan kursor delta.
                if coverage != "date_window" and (
                    current_newest is None or newest_time > current_newest
                ):
                    row.newest_crawled_at = newest_time
                    row.newest_crawled_precision = newest_precision
                current_oldest = as_utc(row.oldest_crawled_at)
                if current_oldest is None or oldest_time < current_oldest:
                    row.oldest_crawled_at = oldest_time
            row.last_successful_crawl_at = now
            if expected_review_count is not None:
                row.last_expected_review_count = int(expected_review_count)
            if coverage == "full_backfill" and complete:
                row.backfill_completed_at = now
            if swept:
                row.last_sweep_at = now
            session.commit()
            return self.serialize(row)

    def record_window(
        self,
        crawl_target: CrawlTarget,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        completeness: str,
        stop_reason: str | None,
        now: datetime,
    ) -> None:
        with self.session_factory() as session:
            row = session.get(self._model(crawl_target), crawl_target.id)
            if row is None:
                return
            session.add(
                CrawlWindowLog(
                    company_id=row.company_id,
                    location_id=row.id if crawl_target.kind == "location" else None,
                    competitor_id=(
                        row.id if crawl_target.kind == "competitor" else None
                    ),
                    date_from=date_from,
                    date_to=date_to,
                    completeness=completeness,
                    stop_reason=stop_reason,
                    finished_at=now,
                )
            )
            session.commit()
