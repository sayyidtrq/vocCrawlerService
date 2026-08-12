from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.session import get_session_factory
from app.integrations.selenium_google_maps_client import (
    SeleniumGoogleMapsReviewClient,
)
from app.services.entitlement_service import EntitlementService
from app.services.fetch_log_service import FetchLogService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.utils.date_parser import is_within_date_range


logger = logging.getLogger(__name__)


class SeleniumFetchService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: SeleniumGoogleMapsReviewClient | None = None,
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
        self.client = client or SeleniumGoogleMapsReviewClient(self.settings)
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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
    ) -> dict:
        location = self.location_service.get_location(location_id)
        if location is None:
            raise ValueError("Location not found.")
        requested_target = self.validate_target(
            target or location.target_review_count
        )
        result = {
            "location_id": location.id,
            "location_name": location.branch_name,
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
                "target_review_count": requested_target,
                "headless": self.settings.selenium_headless,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        }
        log_id = self.fetch_log_service.start_log(
            location.id, self.client.source_name, result["metadata"]
        )
        logger.info(
            "Selenium fetch started for %s with target %s",
            location.branch_name,
            requested_target,
        )
        try:
            raw_reviews = self.client.fetch_reviews(
                location,
                limit=requested_target,
                on_progress=on_progress,
                date_from=date_from,
                date_to=date_to,
            )
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"]["date_from"] = date_from.isoformat() if date_from else None
            result["metadata"]["date_to"] = date_to.isoformat() if date_to else None
            result["total_fetched"] = len(raw_reviews)
            result["total_failed"] = int(
                result["metadata"].get("failed_review_cards", 0)
            )
            for raw_review in raw_reviews:
                try:
                    normalized = self.normalizer.normalize_review(
                        location, raw_review
                    )
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
                    logger.exception(
                        "Failed to store one Selenium review: %s", exc
                    )
            result["metadata"]["matched_review_cards"] = max(
                0, result["total_fetched"] - result["total_skipped_out_of_range"]
            )
            result["metadata"].setdefault(
                "reviews_scanned",
                result["metadata"].get("loaded_review_cards", result["total_fetched"]),
            )
            stopped_reason = result["metadata"].get("stopped_reason")
            range_requested = date_from is not None or date_to is not None
            zero_saved = (
                result["total_inserted"] == 0
                and result["total_duplicate"] == 0
            )
            partial = (
                result["total_fetched"] < requested_target
                or result["total_failed"] > 0
                or stopped_reason in {"sort_unavailable", "time_limit", "max_scanned_reached"}
                or (
                    range_requested
                    and zero_saved
                    and result["total_skipped_out_of_range"] > 0
                )
            )
            result["status"] = "partial_success" if partial else "success"
            if stopped_reason == "sort_unavailable":
                result["error_message"] = result["metadata"].get("range_warning")
        except Exception as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            logger.exception("Selenium fetch failed for %s", location.branch_name)
        finally:
            self.fetch_log_service.finish_log(log_id, result)
        return result

    def validate_target(self, target: object) -> int:
        try:
            value = int(target)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        maximum = min(self.settings.selenium_max_target_reviews, 300)
        if self.company_id is not None:
            quota = EntitlementService(self.company_id, self.session_factory).review_quota()
            if quota > 0:
                maximum = min(maximum, quota)
        if not 1 <= value <= maximum:
            raise ValueError(
                f"Target review count must be between 1 and {maximum}."
            )
        return value
