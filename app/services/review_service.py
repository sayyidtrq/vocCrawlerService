from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Review, ReviewAnalysis
from app.db.session import get_session_factory
from app.services.review_repository import (
    ReviewRepository,
    insert_review_optimistically,
)


class ReviewService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        *,
        session: Session | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self._session = session

    @contextmanager
    def _read_session(self):
        if self._session is not None:
            yield self._session
        else:
            with self.session_factory() as session:
                yield session

    def review_hash_exists(self, review_hash: str) -> bool:
        with self.session_factory() as session:
            return (
                ReviewRepository(session, self.company_id).find_id_by_hash(review_hash)
                is not None
            )

    def insert_review(self, data: dict) -> tuple[Review | None, bool]:
        if self.company_id is not None and "company_id" not in data:
            data["company_id"] = self.company_id
        review = Review(**data)
        with self.session_factory() as session:
            repo = ReviewRepository(session, self.company_id)
            return insert_review_optimistically(
                session, review, lambda: repo.find_existing_dedupe_id(review)
            )

    def get_review(self, review_id: int) -> dict | None:
        with self._read_session() as session:
            row = ReviewRepository(
                session, self.company_id
            ).get_with_latest_analysis(review_id)
            return self._row_to_dict(row) if row else None

    def get_reviews(
        self,
        page: int = 1,
        page_size: int = 20,
        location_id: int | None = None,
        rating: int | None = None,
        sentiment: str | None = None,
        keyword: str | None = None,
        latest_first: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[dict], int]:
        with self._read_session() as session:
            rows, total = ReviewRepository(
                session, self.company_id
            ).list_with_latest_analysis(
                page=page,
                page_size=page_size,
                location_id=location_id,
                rating=rating,
                sentiment=sentiment,
                keyword=keyword,
                latest_first=latest_first,
                date_from=date_from,
                date_to=date_to,
            )
            return [self._row_to_dict(row) for row in rows], total

    def get_all_export_rows(self, location_id: int | None = None) -> list[dict]:
        page_size = 500
        page = 1
        output: list[dict] = []
        while True:
            rows, total = self.get_reviews(
                page=page, page_size=page_size, location_id=location_id
            )
            output.extend(rows)
            if len(output) >= total:
                return output
            page += 1

    @staticmethod
    def _row_to_dict(row) -> dict:
        review: Review = row[0]
        branch_name: str = row[1]
        analysis: ReviewAnalysis | None = row[2]
        return {
            "id": review.id,
            "location_id": review.location_id,
            "location": branch_name,
            "source": review.source,
            "external_place_id": review.external_place_id,
            "external_review_id": review.external_review_id,
            "reviewer_name": review.reviewer_name or "Anonymous",
            "reviewer_profile_url": review.reviewer_profile_url,
            "reviewer_photo_url": review.reviewer_photo_url,
            "reviewer_local_guide_level": review.reviewer_local_guide_level,
            "reviewer_total_reviews": review.reviewer_total_reviews,
            "rating": review.rating,
            "review_text": review.review_text,
            "review_time": review.review_time,
            "review_relative_time": review.review_relative_time,
            "review_language": review.review_language,
            "language": review.language,
            "like_count": review.like_count,
            "owner_response_text": review.owner_response_text,
            "owner_response_time": review.owner_response_time,
            "scraped_at": review.scraped_at,
            "raw_payload": review.raw_payload,
            "review_hash": review.review_hash,
            "created_at": review.created_at,
            "analysis_status": review.analysis_status,
            "analyzed": analysis is not None,
            "analysis_id": analysis.id if analysis else None,
            "sentiment": analysis.sentiment if analysis else None,
            "sentiment_score": (
                float(analysis.sentiment_score)
                if analysis and analysis.sentiment_score is not None
                else None
            ),
            "issue_category": analysis.issue_category if analysis else None,
            "urgency": analysis.urgency if analysis else None,
            "summary": analysis.summary if analysis else None,
            "recommended_action": analysis.recommended_action if analysis else None,
            "keywords": analysis.keywords if analysis else [],
            "is_potential_viral": (
                analysis.is_potential_viral if analysis else False
            ),
            "is_patient_safety_issue": (
                analysis.is_patient_safety_issue if analysis else False
            ),
        }
