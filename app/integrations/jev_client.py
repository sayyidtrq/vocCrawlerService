from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.integrations.gemini_client import GeminiClientBase

logger = logging.getLogger(__name__)

TAXONOMY_CATEGORIES = {
    "doctor": "doctor_service",
    "nurse": "nurse_service",
    "registration": "administration",
    "bpjs / insurance administration": "administration",
    "waiting time": "waiting_time",
    "healthcare queue": "waiting_time",
    "service speed": "waiting_time",
    "cleanliness": "cleanliness",
    "facilities": "facility",
    "parking": "parking",
    "price & value": "billing",
    "pharmacy": "pharmacy",
    "emergency / er": "emergency_room",
    "inpatient care": "inpatient",
    "customer service": "customer_service",
    "service quality": "customer_service",
    "digital service": "booking_system",
    "staff attitude": "staff_communication",
    "professionalism": "staff_communication",
    "security": "security",
    "food quality": "food",
}


class JevAiClient(GeminiClientBase):
    def __init__(
        self, settings: Settings, *, http_client: httpx.Client | None = None
    ) -> None:
        self.settings = settings
        self.model_name = settings.jev_engine_version
        self.last_usage: dict[str, int] = {}
        headers = {}
        if settings.jev_api_key:
            headers["Authorization"] = f"Bearer {settings.jev_api_key}"
        self._http = http_client or httpx.Client(
            base_url=settings.jev_base_url.rstrip("/"),
            timeout=settings.jev_timeout_seconds,
            headers=headers,
        )

    def list_models(self) -> list[str]:
        # TypeSafe Jev doesn't have a dynamic engines endpoint listed in standard docs,
        # but we can just return the configured model.
        return [self.model_name]

    def analyze_review(self, review: dict) -> dict:
        text = review.get("review_text") or ""

        # We form the questions for TypeSafe System One API
        payload = {
            "state": text,
            "model": self.model_name,
            "questions": {
                "sentiment": {
                    "type": "choice",
                    "instructions": "What is the primary sentiment of this review?",
                    "criteria": {
                        "positive": "The customer or user is happy or satisfied with the service or product.",
                        "negative": "The customer or user is unhappy, complaining, or angry.",
                        "neutral": "The review is objective or lacks strong emotion.",
                        "mixed": "The review contains both positive and negative points.",
                    },
                },
                "category": {
                    "type": "choice",
                    "instructions": "Which department, aspect, or service category is this review primarily about?",
                    "criteria": {
                        "doctor": "Doctor services, medical consultations",
                        "nurse": "Nurse services, care staff",
                        "registration": "Registration, front desk, check-in, administration",
                        "waiting time": "Waiting times, queues, service speed, delays",
                        "cleanliness": "Cleanliness of the premises, facility, or location",
                        "facilities": "Facilities, rooms, building, amenities",
                        "parking": "Parking area, vehicle access",
                        "price & value": "Billing, cost, price, payments, rates",
                        "pharmacy": "Pharmacy, medicine, product dispensation",
                        "emergency / er": "Emergency room (IGD), urgent escalation",
                        "inpatient care": "Inpatient care (Rawat Inap), room stay",
                        "customer service": "Customer service, overall service quality, helpdesk",
                        "digital service": "Booking system, mobile app, website, online reservations",
                        "staff attitude": "Staff attitude, professionalism, friendliness, courtesy",
                        "security": "Security guards, safety personnel",
                        "food quality": "Food quality, cafeteria, meals, F&B",
                    },
                },
                "is_safety_issue": {
                    "type": "noul",
                    "instructions": "Does this review mention a critical safety issue, physical harm, danger, accident, malpractice, wrong medication, or emergency?",
                },
                "is_viral_risk": {
                    "type": "noul",
                    "instructions": "Does the reviewer threaten to make the issue viral, share it on social media, or report it to the media?",
                },
            },
        }

        # Note: we use "" empty path because the base_url usually includes /v1/systemone
        # If the base url is just https://api.typesafe.ai, we might need the path.
        # Let's check if the base URL ends with systemone.
        path = ""
        if not self._http.base_url.path.endswith("systemone"):
            path = "/v1/systemone"

        response = self._http.post(
            path,
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Jev AI returned HTTP {response.status_code}: {response.text}"
            )

        result_payload = response.json()
        usage = result_payload.get("usage", {})
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        cost = float(usage.get("cost") or 0.0)
        self.last_usage = {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
        }
        return self._to_analysis(result_payload, review)

    @staticmethod
    def _to_analysis(payload: dict, review: dict) -> dict:
        # payload structure: {"answers": {"sentiment": {"choice": "positive", "confidence": 0.9...}, ...}}
        answers = payload.get("answers", {})

        # Extract sentiment
        sentiment_ans = answers.get("sentiment", {})
        sentiment = str(sentiment_ans.get("choice", "unknown")).lower()
        sentiment_score = float(sentiment_ans.get("confidence", 0.0))

        # Extract category
        category_ans = answers.get("category", {})
        raw_category = str(category_ans.get("choice", "other")).lower()
        category = TAXONOMY_CATEGORIES.get(raw_category, "other")
        if sentiment == "positive" and category == "other":
            category = "general_praise"

        # Extract safety and viral risk
        safety_ans = answers.get("is_safety_issue", {})
        safety_prob = float(safety_ans.get("noul", safety_ans.get("probability", 0.0)))
        safety = safety_prob > 0.5

        viral_ans = answers.get("is_viral_risk", {})
        viral_prob = float(viral_ans.get("noul", viral_ans.get("probability", 0.0)))
        viral = viral_prob > 0.5

        rating = review.get("rating")
        urgency = (
            "critical"
            if safety
            else "high"
            if viral or (rating == 1 and sentiment == "negative")
            else "medium"
            if sentiment in {"negative", "mixed"}
            else "low"
        )

        summaries = {
            "negative": "Pelanggan menyampaikan keluhan yang memerlukan tindak lanjut.",
            "mixed": "Pelanggan memberi apresiasi sekaligus menyampaikan kendala.",
            "positive": "Pelanggan menyampaikan pengalaman pelayanan yang positif.",
        }

        return {
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "issue_category": category,
            "urgency": urgency,
            "summary": summaries.get(
                sentiment, "Ulasan belum memiliki aspek yang cukup meyakinkan."
            ),
            "recommended_action": (
                "Tinjau aspek layanan yang terdeteksi dan tindak lanjuti pola serupa."
            ),
            "keywords": [],  # Jev is a decision model, it doesn't extract freeform keywords easily
            "is_potential_viral": viral,
            "is_patient_safety_issue": safety,
            "jev": payload,
        }
