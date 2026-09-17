from __future__ import annotations

import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.integrations.google_places_client import GooglePlacesClient
from app.integrations.mock_review_client import MockReviewClient
from app.integrations.review_source_client import (
    ReviewSourceClient,
    ReviewSourceError,
    UnsupportedReviewClient,
)
from app.services.fetch_log_service import FetchLogService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.services.worklist_sync_service import WorklistSyncError, WorklistSyncService
from app.utils.date_parser import (
    is_within_date_range,
    parse_datetime,
    parse_relative_datetime,
)
from app.utils.hashing import generate_review_hash

logger = logging.getLogger(__name__)


class FetchService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: ReviewSourceClient | None = None,
    ):
        self.company_id = company_id
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.location_service = LocationService(company_id=company_id, session_factory=session_factory)
        self.worklist_sync_service = (
            WorklistSyncService(
                company_id=company_id,
                session_factory=session_factory,
                settings=self.settings,
            )
            if WorklistSyncService.is_configured(self.settings)
            else None
        )
        self.review_service = ReviewService(company_id=company_id, session_factory=session_factory)
        self.fetch_log_service = FetchLogService(company_id=company_id, session_factory=session_factory)
        self.client = client or self._build_client()

    def _build_client(self) -> ReviewSourceClient:
        if self.settings.review_source_mode == "mock":
            return MockReviewClient()
        if self.settings.review_source_mode == "google_places":
            return GooglePlacesClient(self.settings)
        if self.settings.review_source_mode == "google_business_profile":
            return UnsupportedReviewClient(
                "Google Business Profile integration is not implemented yet."
            )
        return UnsupportedReviewClient(
            "Third-party provider is not implemented yet."
        )

    def _fetch_with_retry(self, location) -> list[dict]:
        attempts = max(1, self.settings.fetch_max_retry + 1)
        client = MockReviewClient() if getattr(location, 'is_mock', False) else self.client
        delays = [5, 15, 30]
        for attempt in range(attempts):
            try:
                return client.fetch_reviews(
                    location, limit=self.settings.fetch_limit_per_location
                )
            except ReviewSourceError as exc:
                if not exc.retriable or attempt == attempts - 1:
                    raise
                delay = delays[min(attempt, len(delays) - 1)]
                logger.warning("Fetch retry %s after error: %s", attempt + 1, exc)
                time.sleep(delay)
        return []

    @staticmethod
    def _resolve_review_time(raw_review: dict) -> datetime | None:
        review_time = parse_datetime(raw_review.get("review_time"))
        if review_time is not None:
            return review_time
        relative_time = raw_review.get("review_relative_time")
        if not relative_time:
            return None
        reference = parse_datetime(raw_review.get("scraped_at")) or datetime.now().astimezone()
        return parse_relative_datetime(relative_time, reference)

    def normalize_review(self, location, raw_review: dict) -> dict:
        raw_payload = raw_review.get("raw_payload")
        if not isinstance(raw_payload, dict):
            raw_payload = dict(raw_review)

        rating = raw_review.get("rating")
        try:
            rating = int(rating) if rating not in {None, ""} else None
        except (TypeError, ValueError):
            logger.warning("Invalid rating received: %r", rating)
            rating = None
        if rating is not None and not 1 <= rating <= 5:
            logger.warning("Rating outside 1-5 received: %r", rating)
            rating = None

        normalized = {
            "location_id": location.id,
            "source": str(
                raw_review.get("source") or self.settings.review_source_mode
            ),
            "external_place_id": location.external_place_id,
            "external_review_id": raw_review.get("external_review_id"),
            "reviewer_name": str(
                raw_review.get("reviewer_name") or "Anonymous"
            ).strip(),
            "reviewer_profile_url": raw_review.get("reviewer_profile_url"),
            "reviewer_photo_url": raw_review.get("reviewer_photo_url"),
            "reviewer_local_guide_level": raw_review.get(
                "reviewer_local_guide_level"
            ),
            "reviewer_total_reviews": raw_review.get("reviewer_total_reviews"),
            "rating": rating,
            "review_text": str(raw_review.get("review_text") or ""),
            "review_time": self._resolve_review_time(raw_review),
            "review_time_precision": raw_review.get("review_time_precision"),
            "is_edited": bool(raw_review.get("is_edited")),
            "edited_at": parse_datetime(raw_review.get("edited_at")),
            "review_relative_time": raw_review.get("review_relative_time"),
            "review_language": str(
                raw_review.get("review_language")
                or raw_review.get("language")
                or "unknown"
            ),
            "language": str(raw_review.get("language") or "unknown"),
            "like_count": int(raw_review.get("like_count") or 0),
            "owner_response_text": raw_review.get("owner_response_text"),
            "owner_response_time": parse_datetime(
                raw_review.get("owner_response_time")
            ),
            "scraped_at": parse_datetime(raw_review.get("scraped_at")),
            "raw_payload": raw_payload,
        }
        normalized["review_hash"] = generate_review_hash(normalized)
        return normalized

    def _refresh_worklist(self) -> dict:
        if self.worklist_sync_service is None:
            return {"status": "not_configured"}
        try:
            result = self.worklist_sync_service.refresh()
            logger.info(
                "Worklist refresh status=%s fetched=%s deactivated=%s",
                result.status,
                result.fetched,
                result.deactivated,
            )
            return result.as_dict()
        except WorklistSyncError:
            logger.exception("Worklist refresh failed; crawl run was not started.")
            raise

    def fetch_location(
        self,
        location_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        refresh_worklist: bool = True,
    ) -> dict:
        worklist_result = self._refresh_worklist() if refresh_worklist else {"status": "not_run"}
        location = self.location_service.get_location(location_id)
        if location is None:
            raise ValueError("Location not found.")

        result = self._empty_result(location)
        result["worklist_sync"] = worklist_result
        if getattr(location, 'onebox_connection_id', None) is not None and not location.crawl_enabled:
            result["status"] = "skipped_disabled"
            result["error_message"] = "Location is disabled by the OneBox worklist."
            return result
        if getattr(location, 'onebox_connection_id', None) is not None and not location.ingest_reviews:
            result["status"] = "skipped_ingest_disabled"
            result["error_message"] = "Review ingestion is disabled by the OneBox worklist."
            return result
        result["metadata"] = {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        }
        result["total_skipped_out_of_range"] = 0
        log_id = self.fetch_log_service.start_log(
            location.id, result["source"], result["metadata"]
        )
        logger.info("Fetch started for %s", location.branch_name)
        try:
            raw_reviews = self._fetch_with_retry(location)
            if hasattr(self.client, "last_metadata"):
                result["metadata"] = dict(self.client.last_metadata)
                result["metadata"]["date_from"] = date_from.isoformat() if date_from else None
                result["metadata"]["date_to"] = date_to.isoformat() if date_to else None
                result["total_failed"] = int(
                    result["metadata"].get("failed_review_cards", 0)
                )
            result["total_fetched"] = len(raw_reviews)
            for raw_review in raw_reviews:
                try:
                    normalized = self.normalize_review(location, raw_review)
                    if not is_within_date_range(normalized["review_time"], date_from, date_to):
                        result["total_skipped_out_of_range"] += 1
                        continue
                    _, duplicate = self.review_service.insert_review(normalized)
                    if duplicate:
                        result["total_duplicate"] += 1
                    else:
                        result["total_inserted"] += 1
                except Exception as exc:
                    result["total_failed"] += 1
                    logger.exception("Failed to process one review: %s", exc)

            is_partial_target = bool(
                result.get("metadata")
                and result["total_fetched"]
                < result["metadata"].get("target_review_count", 0)
            )
            result["status"] = (
                "partial_success"
                if result["total_failed"] or is_partial_target
                else "success"
            )
        except Exception as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            logger.exception("Fetch failed for %s", location.branch_name)
        finally:
            self.fetch_log_service.finish_log(log_id, result)
        return result

    def fetch_all_active_locations(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        worklist_result = self._refresh_worklist()
        locations = self.location_service.get_all_locations(
            active_only=True, crawl_enabled_only=True
        )
        if not locations:
            return {
                "worklist_sync": worklist_result,
                "total_locations": 0,
                "success": 0,
                "failed": 0,
                "total_fetched": 0,
                "total_inserted": 0,
                "total_duplicate": 0,
                "results": [],
            }
        summary = {
            "worklist_sync": worklist_result,
            "total_locations": len(locations),
            "success": 0,
            "failed": 0,
            "total_fetched": 0,
            "total_inserted": 0,
            "total_duplicate": 0,
            "results": [],
        }
        for location in locations:
            result = self.fetch_location(location.id, date_from=date_from, date_to=date_to, refresh_worklist=False)
            summary["results"].append(result)
            if result["status"] in {"success", "partial_success"}:
                summary["success"] += 1
            else:
                summary["failed"] += 1
            summary["total_fetched"] += result["total_fetched"]
            summary["total_inserted"] += result["total_inserted"]
            summary["total_duplicate"] += result["total_duplicate"]
        return summary

    def dry_run_location(
        self,
        location_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        location = self.location_service.get_location(location_id)
        if location is None:
            raise ValueError("Location not found.")
        raw_reviews = self._fetch_with_retry(location)
        normalized = [
            self.normalize_review(location, raw_review) for raw_review in raw_reviews
        ]
        in_range = [
            item for item in normalized
            if is_within_date_range(item["review_time"], date_from, date_to)
        ]
        self.fetch_log_service.create_dry_run_log(
            location.id, self.settings.review_source_mode, len(normalized)
        )
        return {
            "location_id": location.id,
            "location_name": location.branch_name,
            "source": self.settings.review_source_mode,
            "status": "dry_run",
            "total_fetched": len(normalized),
            "total_in_range": len(in_range),
            "samples": in_range[:5],
        }

    def _empty_result(self, location) -> dict:
        source = getattr(
            self.client, "source_name", self.settings.review_source_mode
        )
        return {
            "location_id": location.id,
            "location_name": location.branch_name,
            "source": source,
            "status": "failed",
            "total_fetched": 0,
            "total_inserted": 0,
            "total_duplicate": 0,
            "total_failed": 0,
            "error_message": None,
            "metadata": {},
        }
