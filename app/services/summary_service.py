from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.summary_repository import SummaryRepository


class SummaryService:
    def __init__(self, company_id: int | None = None, *, session: Session):
        self.company_id = company_id
        self.session = session
        self.repository = SummaryRepository(session, company_id)

    def overall_summary(self) -> dict:
        total_locations, total_reviews, analyzed = self.repository.overall_counts()
        total_locations = int(total_locations or 0)
        total_reviews = int(total_reviews or 0)
        analyzed = int(analyzed or 0)
        sentiment_rows = self.repository.sentiment_breakdown()
        issue_rows = self.repository.top_issues()
        critical_count = int(self.repository.critical_issue_count() or 0)
        latest_fetch = self.repository.latest_fetch_at()

        sentiments = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "mixed": 0,
            "unknown": 0,
        }
        sentiments.update({key or "unknown": count for key, count in sentiment_rows})
        return {
            "total_locations": total_locations,
            "total_reviews": total_reviews,
            "analyzed_reviews": analyzed,
            "pending_analysis": total_reviews - analyzed,
            "sentiments": sentiments,
            "top_issues": issue_rows,
            "critical_issues": critical_count,
            "latest_fetch": latest_fetch,
        }

    def location_summary(self, location_id: int) -> dict:
        location = self.repository.get_location(location_id)
        if location is None or (
            self.company_id is not None and location.company_id != self.company_id
        ):
            raise ValueError("Location not found.")
        total_reviews, average_rating = self.repository.location_review_stats(
            location_id
        )
        sentiment_rows = self.repository.location_sentiment_breakdown(location_id)
        issue_rows = self.repository.location_top_issues(location_id)
        critical_count = int(
            self.repository.location_critical_issue_count(location_id) or 0
        )
        negative_examples = self.repository.location_negative_examples(location_id)
        focus = self.repository.location_management_focus(location_id)

        sentiments = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "mixed": 0,
            "unknown": 0,
        }
        sentiments.update({key or "unknown": count for key, count in sentiment_rows})
        return {
            "location_id": location.id,
            "location_name": location.branch_name,
            "total_reviews": int(total_reviews or 0),
            "average_rating": (
                round(float(average_rating), 2) if average_rating is not None else None
            ),
            "sentiments": sentiments,
            "top_issues": issue_rows,
            "critical_issues": critical_count,
            "negative_examples": list(negative_examples),
            "management_focus": list(focus),
        }

    def critical_issues(self) -> list[dict]:
        return [
            {
                "location": location_name,
                "rating": review.rating,
                "review_text": review.review_text,
                "sentiment": analysis.sentiment,
                "issue_category": analysis.issue_category,
                "urgency": analysis.urgency,
                "recommended_action": analysis.recommended_action,
            }
            for review, location_name, analysis in self.repository.critical_issue_rows()
        ]

    def negative_reviews(self) -> list[dict]:
        return [
            {
                "location": location_name,
                "rating": review.rating,
                "review_text": review.review_text,
                "issue_category": analysis.issue_category,
                "urgency": analysis.urgency,
            }
            for review, location_name, analysis in self.repository.negative_review_rows()
        ]
