from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.models import FetchLog, Location, Review
from app.integrations.google_places_client import GooglePlacesClient
from app.integrations.review_source_client import ReviewSourceError
from app.services.crawl_coverage import CrawlCoverageStore, as_utc

logger = logging.getLogger(__name__)


class ReviewTargetNotFound(Exception):
    """Lokasi tidak ada, atau bukan milik tenant ini."""


class ReviewCountProbe:
    """Penanda murah "ada ulasan baru?" dan perkiraan biaya (spec CS-4, CS-5).

    Probe memanggil Google Places satu kali. Estimate tidak memanggil apa pun.
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        places_client: GooglePlacesClient | None = None,
    ):
        self.session_factory = session_factory
        self.settings = settings
        self._places_client = places_client

    @property
    def places_client(self) -> GooglePlacesClient:
        if self._places_client is None:
            self._places_client = GooglePlacesClient(self.settings)
        return self._places_client

    @staticmethod
    def _location(session: Session, company_id: int, onebox_location_id: int) -> Location:
        location = session.scalar(
            select(Location).where(
                Location.company_id == company_id,
                Location.onebox_location_id == onebox_location_id,
            )
        )
        if location is None:
            raise ReviewTargetNotFound(onebox_location_id)
        return location

    def probe(self, company_id: int, onebox_location_id: int) -> dict:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            location = self._location(session, company_id, onebox_location_id)
            previous = location.last_probed_review_count
            place_id = (location.external_place_id or "").strip()
            data = {
                "onebox_location_id": onebox_location_id,
                "changed": True,
                "review_count": None,
                "previous_review_count": previous,
                "probed_at": now.isoformat(),
            }
            try:
                count = self.places_client.review_count(place_id)
            except ReviewSourceError as exc:
                # Gagal terbuka: probe yang gagal tidak boleh menahan crawl.
                logger.warning("Review count probe failed for %s: %s", place_id, exc)
                data["error"] = "PROBE_UNAVAILABLE"
                return data
            data["review_count"] = count
            data["changed"] = count is None or previous is None or count != previous
            location.last_probed_review_count = count
            location.last_probed_at = now
            session.commit()
            return data

    def estimate(self, company_id: int, onebox_location_id: int) -> dict:
        with self.session_factory() as session:
            location = self._location(session, company_id, onebox_location_id)
            probed_at = as_utc(location.last_probed_at)
            crawled_at = as_utc(location.last_successful_crawl_at)
            expected, source, observed_at = None, None, None
            if location.last_probed_review_count is not None and (
                location.last_expected_review_count is None
                or crawled_at is None
                or (probed_at is not None and probed_at >= crawled_at)
            ):
                expected = location.last_probed_review_count
                source, observed_at = "probe", probed_at
            elif location.last_expected_review_count is not None:
                expected = location.last_expected_review_count
                source, observed_at = "snapshot", crawled_at
            stored = session.scalar(
                select(func.count(Review.id)).where(Review.location_id == location.id)
            )
            return {
                "onebox_location_id": onebox_location_id,
                "expected_review_count": expected,
                "expected_source": source,
                "place_rating": self._latest_rating(session, location.id),
                "observed_at": observed_at.isoformat() if observed_at else None,
                "stored_review_count": int(stored or 0),
                "coverage": CrawlCoverageStore.serialize(location),
            }

    @staticmethod
    def _latest_rating(session: Session, location_id: int) -> float | None:
        metadata = session.scalar(
            select(FetchLog.metadata_json)
            .where(FetchLog.location_id == location_id)
            .order_by(FetchLog.id.desc())
            .limit(1)
        )
        snapshot = (metadata or {}).get("rating_snapshot") or {}
        rating = snapshot.get("place_rating")
        return float(rating) if rating is not None else None
