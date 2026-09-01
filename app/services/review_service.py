from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Location, Review, ReviewAnalysis
from app.db.session import get_session_factory


def latest_analysis_subquery():
    return (
        select(
            ReviewAnalysis.review_id.label("review_id"),
            func.max(ReviewAnalysis.id).label("analysis_id"),
        )
        .group_by(ReviewAnalysis.review_id)
        .subquery()
    )


class ReviewService:
    def __init__(self, company_id: int | None = None, session_factory: sessionmaker[Session] | None = None):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()

    def review_hash_exists(self, review_hash: str) -> bool:
        with self.session_factory() as session:
            statement = select(Review.id).where(Review.review_hash == review_hash)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            return session.scalar(statement) is not None

    def insert_review(self, data: dict) -> tuple[Review | None, bool]:
        if self.company_id is not None and "company_id" not in data:
            data["company_id"] = self.company_id
        review = Review(**data)
        with self.session_factory() as session:
            statement = self._dedupe_statement(review)
            existing = session.scalar(statement)
            if existing is not None:
                return None, True
            try:
                session.add(review)
                session.commit()
                session.refresh(review)
                return review, False
            except IntegrityError:
                session.rollback()
                existing = session.scalar(statement)
                if existing is not None:
                    return None, True
                raise

    def _dedupe_statement(self, review: Review):
        predicates = [Review.review_hash == review.review_hash]
        external_review_id = (review.external_review_id or "").strip()
        if external_review_id:
            identity = [
                Review.source == review.source,
                Review.external_review_id == external_review_id,
            ]
            if review.external_place_id:
                identity.append(Review.external_place_id == review.external_place_id)
            else:
                identity.append(Review.location_id == review.location_id)
            predicates.append(and_(*identity))
        statement = select(Review.id).where(or_(*predicates))
        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
        return statement

    def get_review(self, review_id: int) -> dict | None:
        with self.session_factory() as session:
            latest = latest_analysis_subquery()
            statement = (
                select(Review, Location.branch_name, ReviewAnalysis)
                .join(Location, Location.id == Review.location_id)
                .outerjoin(latest, latest.c.review_id == Review.id)
                .outerjoin(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
                .where(Review.id == review_id)
            )
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            row = session.execute(statement).first()
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
        latest = latest_analysis_subquery()
        statement = (
            select(Review, Location.branch_name, ReviewAnalysis)
            .join(Location, Location.id == Review.location_id)
            .outerjoin(latest, latest.c.review_id == Review.id)
            .outerjoin(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
        )
        count_statement = select(func.count(Review.id)).select_from(Review)

        if sentiment:
            count_statement = (
                count_statement.join(latest, latest.c.review_id == Review.id)
                .join(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
                .where(ReviewAnalysis.sentiment == sentiment)
            )
            statement = statement.where(ReviewAnalysis.sentiment == sentiment)
        if location_id is not None:
            statement = statement.where(Review.location_id == location_id)
            count_statement = count_statement.where(Review.location_id == location_id)
        if rating is not None:
            statement = statement.where(Review.rating == rating)
            count_statement = count_statement.where(Review.rating == rating)
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(Review.review_text.ilike(pattern))
            count_statement = count_statement.where(Review.review_text.ilike(pattern))
        if date_from is not None:
            statement = statement.where(Review.review_time >= date_from)
            count_statement = count_statement.where(Review.review_time >= date_from)
        if date_to is not None:
            statement = statement.where(Review.review_time <= date_to)
            count_statement = count_statement.where(Review.review_time <= date_to)

        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
            count_statement = count_statement.where(Review.company_id == self.company_id)

        if latest_first:
            statement = statement.order_by(
                Review.review_time.desc().nullslast(), Review.id.desc()
            )
        else:
            statement = statement.order_by(Review.id.desc())
        statement = statement.offset((page - 1) * page_size).limit(page_size)

        with self.session_factory() as session:
            total = int(session.scalar(count_statement) or 0)
            rows = session.execute(statement).all()
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
