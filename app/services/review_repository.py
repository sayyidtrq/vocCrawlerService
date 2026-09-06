from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from sqlalchemy import and_, func, or_, select
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Location, Review, ReviewAnalysis

ReviewT = TypeVar("ReviewT")


def insert_review_optimistically(
    session: Session,
    review: ReviewT,
    find_existing: Callable[[], int | None],
) -> tuple[ReviewT | None, bool]:
    if find_existing() is not None:
        return None, True
    try:
        session.add(review)
        session.commit()
        session.refresh(review)
        return review, False
    except IntegrityError:
        session.rollback()
        if find_existing() is not None:
            return None, True
        raise


def latest_analysis_subquery():
    return (
        select(
            ReviewAnalysis.review_id.label("review_id"),
            func.max(ReviewAnalysis.id).label("analysis_id"),
        )
        .group_by(ReviewAnalysis.review_id)
        .subquery()
    )


class ReviewRepository:
    def __init__(self, session: Session, company_id: int | None = None):
        self.session = session
        self.company_id = company_id

    def find_id_by_hash(self, review_hash: str) -> int | None:
        statement = select(Review.id).where(Review.review_hash == review_hash)
        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
        return self.session.scalar(statement)

    def find_existing_dedupe_id(self, review: Review) -> int | None:
        return self.session.scalar(self._dedupe_statement(review))

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

    def get_with_latest_analysis(self, review_id: int) -> Row | None:
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
        return self.session.execute(statement).first()

    def list_with_latest_analysis(
        self,
        *,
        page: int,
        page_size: int,
        location_id: int | None,
        rating: int | None,
        sentiment: str | None,
        keyword: str | None,
        latest_first: bool,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> tuple[list[Row], int]:
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
            count_statement = count_statement.where(
                Review.company_id == self.company_id
            )

        if latest_first:
            statement = statement.order_by(
                Review.review_time.desc().nullslast(), Review.id.desc()
            )
        else:
            statement = statement.order_by(Review.id.desc())
        statement = statement.offset((page - 1) * page_size).limit(page_size)

        total = int(self.session.scalar(count_statement) or 0)
        rows = self.session.execute(statement).all()
        return rows, total
