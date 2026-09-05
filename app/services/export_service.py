from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.session import get_session_factory
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.services.summary_service import SummaryService


logger = logging.getLogger(__name__)


class ExportService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
    ):
        self.company_id = company_id
        self.settings = settings or get_settings()
        self.session_factory = session_factory or get_session_factory()
        self.review_service = ReviewService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.location_service = LocationService(
            company_id=company_id, session_factory=self.session_factory
        )

    def export_all_reviews_csv(self) -> Path:
        rows = self.review_service.get_all_export_rows()
        return self._write_review_csv(
            rows, f"reviews_all_{self._timestamp()}.csv"
        )

    def export_location_reviews_csv(self, location_id: int) -> Path:
        if self.location_service.get_location(location_id) is None:
            raise ValueError("Location not found.")
        rows = self.review_service.get_all_export_rows(location_id=location_id)
        return self._write_review_csv(
            rows, f"reviews_location_{location_id}_{self._timestamp()}.csv"
        )

    def export_analysis_summary_csv(self) -> Path:
        locations = self.location_service.get_all_locations()
        path = self._path(f"analysis_summary_{self._timestamp()}.csv")
        fields = [
            "location_id",
            "location_name",
            "total_reviews",
            "average_rating",
            "positive",
            "neutral",
            "negative",
            "mixed",
            "critical_issues",
            "top_issue_categories",
            "management_focus",
        ]
        with self.session_factory() as session:
            summary_service = SummaryService(
                company_id=self.company_id, session=session
            )
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                for location in locations:
                    summary = summary_service.location_summary(location.id)
                    writer.writerow(
                        {
                            "location_id": location.id,
                            "location_name": location.branch_name,
                            "total_reviews": summary["total_reviews"],
                            "average_rating": summary["average_rating"],
                            "positive": summary["sentiments"]["positive"],
                            "neutral": summary["sentiments"]["neutral"],
                            "negative": summary["sentiments"]["negative"],
                            "mixed": summary["sentiments"]["mixed"],
                            "critical_issues": summary["critical_issues"],
                            "top_issue_categories": "; ".join(
                                f"{category}:{count}"
                                for category, count in summary["top_issues"]
                            ),
                            "management_focus": "; ".join(
                                summary["management_focus"]
                            ),
                        }
                    )
        logger.info("Analysis summary exported to %s", path)
        return path

    def export_raw_reviews_json(self) -> Path:
        rows = self.review_service.get_all_export_rows()
        payload = [
            {
                "review_id": row["id"],
                "location_id": row["location_id"],
                "location": row["location"],
                "source": row["source"],
                "raw_payload": row["raw_payload"],
            }
            for row in rows
        ]
        path = self._path(f"raw_reviews_{self._timestamp()}.json")
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Raw reviews exported to %s", path)
        return path

    def _write_review_csv(self, rows: list[dict], filename: str) -> Path:
        path = self._path(filename)
        fields = [
            "id",
            "location_id",
            "location",
            "source",
            "external_review_id",
            "reviewer_name",
            "reviewer_profile_url",
            "reviewer_photo_url",
            "reviewer_local_guide_level",
            "reviewer_total_reviews",
            "rating",
            "review_text",
            "review_time",
            "review_relative_time",
            "review_language",
            "language",
            "like_count",
            "owner_response_text",
            "owner_response_time",
            "scraped_at",
            "sentiment",
            "sentiment_score",
            "issue_category",
            "urgency",
            "summary",
            "recommended_action",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field) for field in fields})
        logger.info("Reviews exported to %s", path)
        return path

    def _path(self, filename: str) -> Path:
        return self.settings.ensure_export_dir() / filename

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")
