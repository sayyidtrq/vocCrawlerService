from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Review, ReviewAnalysis
from app.db.session import get_session_factory
from app.integrations.gemini_client import GeminiClientBase
from app.integrations.local_llm_client import LocalLLMClient


logger = logging.getLogger(__name__)
RATING_FALLBACK_MODEL = "rating-fallback-v1"
ALLOWED_SENTIMENTS = {"positive", "neutral", "negative", "mixed", "unknown"}
ALLOWED_URGENCIES = {"low", "medium", "high", "critical", "unknown"}
ALLOWED_CATEGORIES = {
    "doctor_service",
    "nurse_service",
    "administration",
    "waiting_time",
    "cleanliness",
    "facility",
    "parking",
    "billing",
    "pharmacy",
    "emergency_room",
    "inpatient",
    "customer_service",
    "booking_system",
    "staff_communication",
    "security",
    "food",
    "general_praise",
    "other",
}
ANALYSIS_STATUSES = {"pending", "completed", "failed", "incomplete"}
REQUIRED_ANALYSIS_FIELDS = (
    "urgency",
    "issue_category",
    "summary",
    "recommended_action",
)


class AnalysisService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: GeminiClientBase | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        if client:
            self.client = client
        else:
            self.client = LocalLLMClient(self.settings)

    def analyze_pending(
        self, location_id: int | None = None, rating: int | None = None
    ) -> dict:
        pending_exists = exists(
            select(ReviewAnalysis.id).where(ReviewAnalysis.review_id == Review.id)
        )
        statement = select(Review).where(~pending_exists).order_by(Review.id)
        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
        if location_id is not None:
            statement = statement.where(Review.location_id == location_id)
        if rating is not None:
            statement = statement.where(Review.rating == rating)
        with self.session_factory() as session:
            reviews = list(session.scalars(statement))
            review_data = [self._review_to_dict(review) for review in reviews]
        return self._analyze_items(review_data)

    def rerun_review(self, review_id: int) -> dict:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            review = session.scalar(statement)
            if review is None:
                raise ValueError("Review not found.")
            review_data = self._review_to_dict(review)
        return self._analyze_items([review_data])

    def rerun_location(self, location_id: int) -> dict:
        with self.session_factory() as session:
            statement = (
                select(Review)
                .where(Review.location_id == location_id)
                .order_by(Review.id)
            )
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            reviews = list(session.scalars(statement))
            review_data = [self._review_to_dict(review) for review in reviews]
        return self._analyze_items(review_data)

    def _analyze_items(self, reviews: list[dict]) -> dict:
        result = {
            "total": len(reviews),
            "success": 0,
            "failed": 0,
            "skipped_empty": 0,
            "rating_fallback": 0,
            "sentiments": {
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "mixed": 0,
                "unknown": 0,
            },
            "errors": [],
            "tokens_used": 0,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
        batch_size = max(1, self.settings.analysis_batch_size)
        for start in range(0, len(reviews), batch_size):
            for review in reviews[start : start + batch_size]:
                if not review["review_text"].strip():
                    raw_result = self._rating_only_result(review.get("rating"))
                    cleaned = self._validate_result(raw_result)
                    self._store_analysis(
                        review["id"],
                        cleaned,
                        raw_result,
                        model_name=RATING_FALLBACK_MODEL,
                    )
                    result["success"] += 1
                    result["rating_fallback"] += 1
                    result["sentiments"][cleaned["sentiment"]] += 1
                    continue
                try:
                    raw_result = self.client.analyze_review(review)
                    usage = getattr(self.client, "last_usage", {}) or {}
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        result["token_usage"][key] += int(usage.get(key, 0) or 0)
                    result["tokens_used"] = result["token_usage"]["total_tokens"]
                    cleaned = self._validate_result(raw_result)
                    self._store_analysis(review["id"], cleaned, raw_result)
                    result["success"] += 1
                    result["sentiments"][cleaned["sentiment"]] += 1
                except Exception:
                    self._store_failure_status(review["id"])
                    result["failed"] += 1
                    result["errors"].append(
                        {"review_id": review["id"], "error": "Analysis failed."}
                    )
                    logger.exception("Analysis failed for review %s", review["id"])
        return result

    def _store_analysis(
        self,
        review_id: int,
        cleaned: dict,
        raw_result: dict,
        model_name: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            if session.bind.dialect.name == "postgresql":
                # Serialise against a concurrent analysis of the same review so the
                # two cannot interleave and leave the watermark behind the newer
                # analysis row. SQLite has no row locks and no concurrent writers.
                statement = statement.with_for_update()

            review = session.scalar(statement)
            if review is None:
                raise ValueError(f"Review {review_id} not found in this company.")

            session.add(
                ReviewAnalysis(
                    review_id=review_id,
                    sentiment=cleaned["sentiment"],
                    sentiment_score=cleaned["sentiment_score"],
                    issue_category=cleaned["issue_category"],
                    urgency=cleaned["urgency"],
                    summary=cleaned["summary"],
                    recommended_action=cleaned["recommended_action"],
                    keywords=cleaned["keywords"],
                    is_potential_viral=cleaned["is_potential_viral"],
                    is_patient_safety_issue=cleaned["is_patient_safety_issue"],
                    model_name=model_name or self.client.model_name,
                    prompt_version=self.settings.prompt_version,
                    raw_response=raw_result,
                )
            )
            review.analysis_status = self._result_status(cleaned)
            # Same transaction as the insert, deliberately. If the analysis
            # committed and the watermark did not, the review would sit below every
            # consumer's checkpoint forever and its analysis would never be
            # delivered — silent permanent data loss rather than a retryable error.
            #
            # Postgres: clock_timestamp(), not now(), which is frozen at
            # transaction start and would hand two analyses in one batch the same
            # watermark. SQLite (tests only) has no clock_timestamp, and its
            # CURRENT_TIMESTAMP drops microseconds — since SQLAlchemy stores
            # DATETIME as text, a second-precision value sorts as a prefix of a
            # microsecond one and would corrupt the keyset ordering. Use the Python
            # clock there instead; the single-process test has no skew to worry about.
            review.sync_updated_at = (
                func.clock_timestamp()
                if session.bind.dialect.name == "postgresql"
                else datetime.now(timezone.utc)
            )
            session.commit()

    def _store_failure_status(self, review_id: int) -> None:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            if session.bind.dialect.name == "postgresql":
                statement = statement.with_for_update()

            review = session.scalar(statement)
            if review is None:
                raise ValueError(f"Review {review_id} not found in this company.")

            review.analysis_status = "failed"
            review.sync_updated_at = (
                func.clock_timestamp()
                if session.bind.dialect.name == "postgresql"
                else datetime.now(timezone.utc)
            )
            session.commit()

    @staticmethod
    def _result_status(result: dict) -> str:
        return (
            "completed"
            if all(str(result.get(field) or "").strip() for field in REQUIRED_ANALYSIS_FIELDS)
            else "incomplete"
        )

    @staticmethod
    def _rating_only_result(rating: int | None) -> dict:
        if rating is None:
            sentiment = "unknown"
            score = 0.0
            urgency = "unknown"
            summary = "Reviewer tidak menulis komentar dan rating tidak tersedia."
            action = "Tandai sebagai masukan tanpa konteks dan pantau pola serupa."
        elif rating <= 2:
            sentiment = "negative"
            score = 0.85
            urgency = "medium"
            summary = f"Reviewer memberikan rating {rating}/5 tanpa komentar tertulis."
            action = (
                "Tindak lanjuti rating rendah bila identitas reviewer tersedia dan "
                "pantau pola serupa pada lokasi ini."
            )
        elif rating == 3:
            sentiment = "neutral"
            score = 0.75
            urgency = "low"
            summary = "Reviewer memberikan rating 3/5 tanpa komentar tertulis."
            action = "Pantau pola rating dan kumpulkan konteks tambahan bila tersedia."
        else:
            sentiment = "positive"
            score = 0.85
            urgency = "low"
            summary = f"Reviewer memberikan rating {rating}/5 tanpa komentar tertulis."
            action = "Pertahankan mutu layanan dan pantau konsistensi rating."

        return {
            "sentiment": sentiment,
            "sentiment_score": score,
            "issue_category": "other",
            "urgency": urgency,
            "summary": summary,
            "recommended_action": action,
            "keywords": [],
            "is_potential_viral": False,
            "is_patient_safety_issue": False,
            "analysis_source": RATING_FALLBACK_MODEL,
        }

    @staticmethod
    def _review_to_dict(review: Review) -> dict:
        return {
            "id": review.id,
            "rating": review.rating,
            "review_text": review.review_text,
            "reviewer_name": review.reviewer_name,
            "review_time": review.review_time,
            "location_id": review.location_id,
        }

    @staticmethod
    def _validate_result(result: dict) -> dict:
        sentiment = str(result.get("sentiment") or "unknown").lower()
        if sentiment not in ALLOWED_SENTIMENTS:
            sentiment = "unknown"
        urgency = str(result.get("urgency") or "unknown").lower()
        if urgency not in ALLOWED_URGENCIES:
            urgency = "unknown"
        category = str(result.get("issue_category") or "other").lower()
        if category not in ALLOWED_CATEGORIES:
            category = "other"
        try:
            score = float(result.get("sentiment_score", 0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))
        keywords = result.get("keywords")
        if not isinstance(keywords, list):
            keywords = []
        return {
            "sentiment": sentiment,
            "sentiment_score": score,
            "issue_category": category,
            "urgency": urgency,
            "summary": str(result.get("summary") or ""),
            "recommended_action": str(result.get("recommended_action") or ""),
            "keywords": [str(keyword) for keyword in keywords],
            "is_potential_viral": bool(result.get("is_potential_viral", False)),
            "is_patient_safety_issue": bool(
                result.get("is_patient_safety_issue", False)
            ),
        }
