from __future__ import annotations

import httpx

from app.config import Settings
from app.integrations.gemini_client import GeminiClientBase

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


class AbsaClient(GeminiClientBase):
    def __init__(
        self, settings: Settings, *, http_client: httpx.Client | None = None
    ) -> None:
        self.settings = settings
        self.model_name = settings.absa_engine_version
        self.last_usage: dict[str, int] = {}
        self._http = http_client or httpx.Client(
            base_url=settings.absa_base_url.rstrip("/"),
            timeout=settings.absa_timeout_seconds,
        )

    def list_models(self) -> list[str]:
        response = self._http.get("/inference/engines")
        response.raise_for_status()
        engines = response.json().get("engines", [])
        return sorted(
            str(item["id"])
            for item in engines
            if item.get("available") and item.get("id")
        )

    def analyze_review(self, review: dict) -> dict:
        response = self._http.post(
            "/inference/single",
            json={
                "review": review.get("review_text") or "",
                "engine_version": self.model_name,
                "profile": self.settings.absa_profile,
                "confidence_threshold": self.settings.absa_confidence_threshold,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"ABSA returned HTTP {response.status_code}.")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise TypeError("ABSA returned an invalid response.")
        return self._to_analysis(payload, review)

    @staticmethod
    def _to_analysis(payload: dict, review: dict) -> dict:
        aspects = payload.get("results") or []
        sentiments = {
            str(item.get("sentiment") or "").lower()
            for item in aspects
            if item.get("sentiment")
        }
        if "positive" in sentiments and "negative" in sentiments:
            sentiment = "mixed"
        elif sentiments:
            sentiment = max(
                aspects,
                key=lambda item: float(item.get("confidence") or 0),
            ).get("sentiment", "unknown").lower()
        else:
            sentiment = "unknown"

        primary = max(
            aspects,
            key=lambda item: (
                item.get("sentiment") == "negative",
                float(item.get("confidence") or 0),
            ),
            default={},
        )
        taxonomy = str(
            primary.get("complaint_taxonomy") or primary.get("taxonomy") or ""
        ).lower()
        category = TAXONOMY_CATEGORIES.get(taxonomy, "other")
        if sentiment == "positive" and category == "other":
            category = "general_praise"

        text = str(review.get("review_text") or "").lower()
        safety = any(
            word in text
            for word in ("salah obat", "malpraktik", "darurat", "nyawa", "infeksi")
        )
        viral = any(word in text for word in ("viral", "sebarkan", "media sosial"))
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
            "negative": "Pasien menyampaikan keluhan yang memerlukan tindak lanjut.",
            "mixed": "Pasien memberi apresiasi sekaligus menyampaikan kendala.",
            "positive": "Pasien menyampaikan pengalaman pelayanan yang positif.",
        }
        keywords = list(
            dict.fromkeys(
                str(value)
                for item in aspects
                for value in (item.get("aspect"), item.get("opinion"))
                if value
            )
        )[:5]
        return {
            "sentiment": sentiment,
            "sentiment_score": max(
                (float(item.get("confidence") or 0) for item in aspects),
                default=0.0,
            ),
            "issue_category": category,
            "urgency": urgency,
            "summary": summaries.get(
                sentiment, "Ulasan belum memiliki aspek yang cukup meyakinkan."
            ),
            "recommended_action": (
                "Tinjau aspek layanan yang terdeteksi dan tindak lanjuti pola serupa."
            ),
            "keywords": keywords,
            "is_potential_viral": viral,
            "is_patient_safety_issue": safety,
            "absa": payload,
        }
