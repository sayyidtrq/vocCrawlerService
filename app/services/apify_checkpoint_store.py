from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Competitor, Location
from app.db.session import get_session_factory
from app.integrations.apify_review_client import SORT_BY_MAP
from app.utils.date_parser import parse_datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApifyCheckpoint:
    sort_by: str
    review_time: datetime
    review_id: str
    recorded_at: datetime


class ApifyCheckpointStore:
    def __init__(self, session_factory: sessionmaker[Session] | None = None):
        self.session_factory = session_factory or get_session_factory()

    def load(self, crawl_target) -> ApifyCheckpoint | None:
        with self.session_factory() as session:
            target = session.get(self._model(crawl_target), crawl_target.id)
            payload = target.apify_resume_checkpoint if target else None
        if not isinstance(payload, dict):
            return None
        review_time = parse_datetime(payload.get("review_time"))
        recorded_at = parse_datetime(payload.get("recorded_at"))
        sort_by = payload.get("sort_by")
        review_id = payload.get("review_id")
        if (
            sort_by not in SORT_BY_MAP
            or review_time is None
            or recorded_at is None
            or not review_id
        ):
            return None
        return ApifyCheckpoint(
            sort_by=str(sort_by),
            review_time=review_time,
            review_id=str(review_id),
            recorded_at=recorded_at,
        )

    def save(self, crawl_target, checkpoint: ApifyCheckpoint) -> None:
        payload = asdict(checkpoint)
        payload["review_time"] = self._iso(checkpoint.review_time)
        payload["recorded_at"] = self._iso(checkpoint.recorded_at)
        with self.session_factory() as session:
            target = session.get(self._model(crawl_target), crawl_target.id)
            if target is None:
                raise ValueError(f"{crawl_target.kind.title()} not found.")
            target.apify_resume_checkpoint = payload
            session.commit()

    def clear(self, crawl_target) -> None:
        with self.session_factory() as session:
            target = session.get(self._model(crawl_target), crawl_target.id)
            if target is None or target.apify_resume_checkpoint is None:
                return
            target.apify_resume_checkpoint = None
            session.commit()

    def resolve_effective_lower_bound(
        self,
        crawl_target,
        requested_sort_by: str,
        requested_date_from: datetime | None,
    ) -> tuple[str, datetime | None]:
        if requested_sort_by not in SORT_BY_MAP:
            raise ValueError(f"Unsupported review sort: {requested_sort_by}.")
        checkpoint = self.load(crawl_target)
        if checkpoint is None:
            return requested_sort_by, requested_date_from
        if checkpoint.sort_by != requested_sort_by:
            logger.warning(
                "Discarding Apify checkpoint sorted by %s because %s was requested.",
                checkpoint.sort_by,
                requested_sort_by,
            )
            self.clear(crawl_target)
            return requested_sort_by, requested_date_from
        if requested_date_from is None:
            return requested_sort_by, checkpoint.review_time
        try:
            lower_bound = max(requested_date_from, checkpoint.review_time)
        except TypeError:
            lower_bound = max(
                self._aware(requested_date_from), self._aware(checkpoint.review_time)
            )
        return requested_sort_by, lower_bound

    @staticmethod
    def _model(crawl_target):
        return Location if crawl_target.kind == "location" else Competitor

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @classmethod
    def _iso(cls, value: datetime) -> str:
        return (
            cls._aware(value)
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
