"""Read-only freshness and reconciliation queries for the audit backup."""

from datetime import datetime, timezone

from sqlalchemy import case, func, or_, select

from app.db.audit_models import AuditAnalysis, AuditCrawlRun, AuditReview
from app.db.session import get_session_factory
from app.services.integration_review_service import IntegrationRequestError

ANALYSED_STATUSES = ("analyzed", "rating_fallback")
MAX_RECONCILE_ROWS = 200000
HASH_CHUNK_SIZE = 500


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age(as_of: datetime, value: datetime | None) -> int | None:
    return int((as_of - _utc(value)).total_seconds()) if value is not None else None


class AuditQueryService:
    def __init__(self, *, session_factory=None, clock=None):
        self.session_factory = session_factory if session_factory is not None else lambda: get_session_factory()()
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def summary(self, site_id: int = 0, place_id: str | None = None, limit: int = 50) -> dict:
        as_of = _utc(self.clock())
        try:
            with self.session_factory() as session, session.no_autoflush:
                if place_id is None:
                    return self._site_summary(session, site_id, limit, as_of)
                return self._place_summary(session, site_id, place_id, as_of)
        except Exception as exc:
            raise IntegrationRequestError(
                503, "AUDIT_UNAVAILABLE", "The audit database is unavailable."
            ) from exc

    @staticmethod
    def _review_stats(site_id: int):
        has_analysis = select(AuditAnalysis.id).where(
            AuditAnalysis.site_id == AuditReview.site_id,
            AuditAnalysis.review_hash == AuditReview.review_hash,
            AuditAnalysis.kind == "analysis",
            # A failed analysis leaves the review without an analysis, so it must not hide it.
            AuditAnalysis.status.in_(ANALYSED_STATUSES),
        ).exists()
        return select(
            AuditReview.place_id,
            func.count(AuditReview.id).label("stored_count"),
            func.max(AuditReview.review_time).label("newest_review_time"),
            func.min(AuditReview.review_time).label("oldest_review_time"),
            func.min(AuditReview.first_seen_at).label("first_seen_at"),
            func.max(AuditReview.last_seen_at).label("last_seen_at"),
            func.count(case((~has_analysis, 1))).label("unanalyzed_count"),
        ).where(AuditReview.site_id == site_id).group_by(AuditReview.place_id)

    @staticmethod
    def _crawl_stats(site_id: int):
        return select(
            AuditCrawlRun.place_id,
            func.count(AuditCrawlRun.id).label("run_count"),
            func.max(AuditCrawlRun.started_at).label("last_crawl_at"),
        ).where(AuditCrawlRun.site_id == site_id).group_by(AuditCrawlRun.place_id)

    def _place_summary(self, session, site_id: int, place_id: str, as_of: datetime) -> dict:
        review_row = session.execute(self._review_stats(site_id).where(
            AuditReview.place_id == place_id
        )).mappings().one_or_none()
        reviews = {key: review_row[key] if review_row is not None else default for key, default in (
            ("stored_count", 0), ("newest_review_time", None), ("oldest_review_time", None),
            ("first_seen_at", None), ("last_seen_at", None), ("unanalyzed_count", 0),
        )}
        reviews["last_seen_age_seconds"] = _age(as_of, reviews["last_seen_at"])
        crawl_row = session.execute(self._crawl_stats(site_id).where(
            AuditCrawlRun.place_id == place_id
        )).mappings().one_or_none()
        last_run = session.execute(select(
            AuditCrawlRun.run_id, AuditCrawlRun.mode, AuditCrawlRun.status,
            AuditCrawlRun.started_at, AuditCrawlRun.finished_at, AuditCrawlRun.fetched_count,
        ).where(
            AuditCrawlRun.site_id == site_id, AuditCrawlRun.place_id == place_id,
        ).order_by(AuditCrawlRun.started_at.desc(), AuditCrawlRun.id.desc()).limit(1)).mappings().one_or_none()
        analysis_rows = session.execute(select(
            AuditAnalysis.status, func.count(AuditAnalysis.id).label("count"),
            func.max(AuditAnalysis.created_at).label("last_analysis_at"),
        ).join(AuditReview, (
            (AuditReview.site_id == AuditAnalysis.site_id)
            & (AuditReview.review_hash == AuditAnalysis.review_hash)
        )).where(
            AuditReview.site_id == site_id, AuditReview.place_id == place_id,
            AuditAnalysis.kind == "analysis",
        ).group_by(AuditAnalysis.status)).mappings().all()
        last_crawl_at = crawl_row["last_crawl_at"] if crawl_row is not None else None
        return {
            "site_id": site_id, "place_id": place_id, "as_of": as_of, "reviews": reviews,
            "crawls": {
                "run_count": crawl_row["run_count"] if crawl_row is not None else 0,
                "last_run": dict(last_run) if last_run is not None else None,
                "last_crawl_at": last_crawl_at, "last_crawl_age_seconds": _age(as_of, last_crawl_at),
            },
            "analyses": {
                "count": sum(row["count"] for row in analysis_rows),
                "last_analysis_at": max((row["last_analysis_at"] for row in analysis_rows), default=None),
                "by_status": {row["status"]: row["count"] for row in analysis_rows},
            },
        }

    def _site_summary(self, session, site_id: int, limit: int, as_of: datetime) -> dict:
        place_ids = select(AuditReview.place_id).where(AuditReview.site_id == site_id).union(
            select(AuditCrawlRun.place_id).where(AuditCrawlRun.site_id == site_id)
        ).subquery()
        reviews = self._review_stats(site_id).subquery()
        crawls = self._crawl_stats(site_id).subquery()
        totals = dict(session.execute(select(
            select(func.count()).select_from(place_ids).scalar_subquery().label("places"),
            select(func.count()).select_from(AuditReview).where(
                AuditReview.site_id == site_id
            ).scalar_subquery().label("reviews"),
            select(func.count()).select_from(AuditCrawlRun).where(
                AuditCrawlRun.site_id == site_id
            ).scalar_subquery().label("runs"),
            select(func.count()).select_from(AuditAnalysis).where(
                AuditAnalysis.site_id == site_id, AuditAnalysis.kind == "analysis",
            ).scalar_subquery().label("analyses"),
        )).mappings().one())
        rows = session.execute(select(
            place_ids.c.place_id,
            func.coalesce(reviews.c.stored_count, 0).label("stored_count"),
            reviews.c.newest_review_time, reviews.c.last_seen_at, crawls.c.last_crawl_at,
            func.coalesce(reviews.c.unanalyzed_count, 0).label("unanalyzed_count"),
        ).select_from(
            place_ids.outerjoin(reviews, reviews.c.place_id == place_ids.c.place_id)
            .outerjoin(crawls, crawls.c.place_id == place_ids.c.place_id)
        ).order_by(
            case((crawls.c.last_crawl_at.is_(None), 0), else_=1),
            crawls.c.last_crawl_at, place_ids.c.place_id,
        ).limit(limit)).mappings().all()
        return {
            "site_id": site_id, "as_of": as_of, "totals": totals,
            "places": [
                {**row, "last_crawl_age_seconds": _age(as_of, row["last_crawl_at"])} for row in rows
            ],
            "total_places": totals["places"], "truncated": totals["places"] > len(rows),
        }

    def reconcile(self, params: dict) -> dict:
        site_id, place_id = params.get("site_id", 0), params["place_id"]
        caller = set(params["review_hashes"])
        since = _utc(params["since"]) if params.get("since") is not None else None
        limit = params.get("limit", 1000)
        as_of = _utc(self.clock())
        filters = [AuditReview.site_id == site_id, AuditReview.place_id == place_id]
        if since is not None:
            filters.append(or_(AuditReview.review_time >= since, AuditReview.review_time.is_(None)))
        try:
            with self.session_factory() as session, session.no_autoflush:
                backup_count = session.scalar(select(func.count()).select_from(AuditReview).where(*filters))
                if backup_count > MAX_RECONCILE_ROWS:
                    raise IntegrationRequestError(
                        400, "RECONCILE_TOO_LARGE", "Too many backup reviews; pass since to restrict the time range."
                    )
                backup = set(session.scalars(select(AuditReview.review_hash).where(*filters)))
                existing = {}
                hashes = sorted(caller)
                for offset in range(0, len(hashes), HASH_CHUNK_SIZE):
                    existing.update(session.execute(select(AuditReview.review_hash, AuditReview.place_id).where(
                        AuditReview.site_id == site_id,
                        AuditReview.review_hash.in_(hashes[offset:offset + HASH_CHUNK_SIZE]),
                    )).tuples().all())
        except IntegrationRequestError:
            raise
        except Exception as exc:
            raise IntegrationRequestError(
                503, "AUDIT_UNAVAILABLE", "The audit database is unavailable."
            ) from exc
        missing_in_caller = sorted(backup - caller)
        missing_in_backup = sorted(caller - existing.keys())
        return {
            "site_id": site_id, "place_id": place_id, "since": since,
            "caller_count": len(caller), "backup_count": backup_count, "matched": len(caller & backup),
            "missing_in_caller": missing_in_caller[:limit], "missing_in_caller_count": len(missing_in_caller),
            "missing_in_caller_truncated": len(missing_in_caller) > limit,
            "missing_in_backup": missing_in_backup[:limit], "missing_in_backup_count": len(missing_in_backup),
            "missing_in_backup_truncated": len(missing_in_backup) > limit,
            "other_place_count": sum(place != place_id for place in existing.values()), "as_of": as_of,
        }
