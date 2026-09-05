from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FetchLog, Location, Review, ReviewAnalysis
from app.services.review_service import latest_analysis_subquery


class SummaryRepository:
    def __init__(self, session: Session, company_id: int | None = None):
        self.session = session
        self.company_id = company_id

    def overall_counts(self) -> tuple[object, object, object]:
        latest = latest_analysis_subquery()

        location_count_stmt = select(func.count(Location.id))
        if self.company_id is not None:
            location_count_stmt = location_count_stmt.where(
                Location.company_id == self.company_id
            )
        total_locations = self.session.scalar(location_count_stmt)

        review_count_stmt = select(func.count(Review.id))
        if self.company_id is not None:
            review_count_stmt = review_count_stmt.where(
                Review.company_id == self.company_id
            )
        total_reviews = self.session.scalar(review_count_stmt)

        analyzed_stmt = select(func.count()).select_from(latest)
        if self.company_id is not None:
            analyzed_stmt = analyzed_stmt.join(
                Review, Review.id == latest.c.review_id
            ).where(Review.company_id == self.company_id)
        analyzed = self.session.scalar(analyzed_stmt)

        return total_locations, total_reviews, analyzed

    def sentiment_breakdown(self) -> list[tuple]:
        latest = latest_analysis_subquery()
        sentiment_stmt = select(
            ReviewAnalysis.sentiment, func.count(ReviewAnalysis.id)
        ).join(latest, latest.c.analysis_id == ReviewAnalysis.id)
        if self.company_id is not None:
            sentiment_stmt = sentiment_stmt.join(
                Review, Review.id == ReviewAnalysis.review_id
            ).where(Review.company_id == self.company_id)
        return self.session.execute(
            sentiment_stmt.group_by(ReviewAnalysis.sentiment)
        ).all()

    def top_issues(self) -> list[tuple]:
        latest = latest_analysis_subquery()
        issue_stmt = select(
            ReviewAnalysis.issue_category, func.count(ReviewAnalysis.id)
        ).join(latest, latest.c.analysis_id == ReviewAnalysis.id)
        if self.company_id is not None:
            issue_stmt = issue_stmt.join(
                Review, Review.id == ReviewAnalysis.review_id
            ).where(Review.company_id == self.company_id)
        return self.session.execute(
            issue_stmt.group_by(ReviewAnalysis.issue_category)
            .order_by(func.count(ReviewAnalysis.id).desc())
            .limit(5)
        ).all()

    def critical_issue_count(self) -> object:
        latest = latest_analysis_subquery()
        critical_stmt = (
            select(func.count(ReviewAnalysis.id))
            .join(latest, latest.c.analysis_id == ReviewAnalysis.id)
            .where(ReviewAnalysis.urgency.in_(["high", "critical"]))
        )
        if self.company_id is not None:
            critical_stmt = critical_stmt.join(
                Review, Review.id == ReviewAnalysis.review_id
            ).where(Review.company_id == self.company_id)
        return self.session.scalar(critical_stmt)

    def latest_fetch_at(self) -> object:
        fetch_stmt = select(func.max(FetchLog.finished_at))
        if self.company_id is not None:
            fetch_stmt = fetch_stmt.where(FetchLog.company_id == self.company_id)
        return self.session.scalar(fetch_stmt)

    def get_location(self, location_id: int) -> Location | None:
        return self.session.get(Location, location_id)

    def location_review_stats(self, location_id: int) -> tuple:
        return self.session.execute(
            select(func.count(Review.id), func.avg(Review.rating)).where(
                Review.location_id == location_id
            )
        ).one()

    def location_sentiment_breakdown(self, location_id: int) -> list[tuple]:
        latest = latest_analysis_subquery()
        return self.session.execute(
            select(ReviewAnalysis.sentiment, func.count(ReviewAnalysis.id))
            .join(latest, latest.c.analysis_id == ReviewAnalysis.id)
            .join(Review, Review.id == ReviewAnalysis.review_id)
            .where(Review.location_id == location_id)
            .group_by(ReviewAnalysis.sentiment)
        ).all()

    def location_top_issues(self, location_id: int) -> list[tuple]:
        latest = latest_analysis_subquery()
        return self.session.execute(
            select(ReviewAnalysis.issue_category, func.count(ReviewAnalysis.id))
            .join(latest, latest.c.analysis_id == ReviewAnalysis.id)
            .join(Review, Review.id == ReviewAnalysis.review_id)
            .where(Review.location_id == location_id)
            .group_by(ReviewAnalysis.issue_category)
            .order_by(func.count(ReviewAnalysis.id).desc())
            .limit(5)
        ).all()

    def location_critical_issue_count(self, location_id: int) -> object:
        latest = latest_analysis_subquery()
        return self.session.scalar(
            select(func.count(ReviewAnalysis.id))
            .join(latest, latest.c.analysis_id == ReviewAnalysis.id)
            .join(Review, Review.id == ReviewAnalysis.review_id)
            .where(
                Review.location_id == location_id,
                ReviewAnalysis.urgency.in_(["high", "critical"]),
            )
        )

    def location_negative_examples(self, location_id: int) -> list[str | None]:
        latest = latest_analysis_subquery()
        return self.session.execute(
            select(Review.review_text)
            .join(latest, latest.c.review_id == Review.id)
            .join(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
            .where(
                Review.location_id == location_id,
                ReviewAnalysis.sentiment == "negative",
            )
            .order_by(Review.id.desc())
            .limit(3)
        ).scalars().all()

    def location_management_focus(self, location_id: int) -> list[str | None]:
        latest = latest_analysis_subquery()
        return self.session.execute(
            select(ReviewAnalysis.recommended_action)
            .join(latest, latest.c.analysis_id == ReviewAnalysis.id)
            .join(Review, Review.id == ReviewAnalysis.review_id)
            .where(
                Review.location_id == location_id,
                ReviewAnalysis.recommended_action.is_not(None),
            )
            .distinct()
            .limit(3)
        ).scalars().all()

    def critical_issue_rows(self) -> list[tuple]:
        latest = latest_analysis_subquery()
        statement = (
            select(Review, Location.branch_name, ReviewAnalysis)
            .join(Location, Location.id == Review.location_id)
            .join(latest, latest.c.review_id == Review.id)
            .join(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
            .where(ReviewAnalysis.urgency.in_(["high", "critical"]))
            .order_by(ReviewAnalysis.urgency, Review.id.desc())
        )
        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
        return self.session.execute(statement).all()

    def negative_review_rows(self) -> list[tuple]:
        latest = latest_analysis_subquery()
        statement = (
            select(Review, Location.branch_name, ReviewAnalysis)
            .join(Location, Location.id == Review.location_id)
            .join(latest, latest.c.review_id == Review.id)
            .join(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
            .where(ReviewAnalysis.sentiment == "negative")
            .order_by(Review.id.desc())
        )
        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
        return self.session.execute(statement).all()
