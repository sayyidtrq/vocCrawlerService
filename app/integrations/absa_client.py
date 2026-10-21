from __future__ import annotations

import httpx

from app.config import Settings
from app.integrations.gemini_client import GeminiClientBase
from app.services.taxonomy_service import Taxonomy

TAXONOMY_CATEGORIES = {
    "doctor": "professional_service",
    "nurse": "staff_service",
    "registration": "administration",
    "bpjs / insurance administration": "administration",
    "waiting time": "waiting_time",
    "healthcare queue": "waiting_time",
    "service speed": "waiting_time",
    "cleanliness": "cleanliness",
    "facilities": "facility",
    "parking": "parking",
    "price & value": "price_value",
    "pharmacy": "availability",
    "emergency / er": "safety_security",
    "inpatient care": "facility",
    "customer service": "customer_service",
    "service quality": "service_quality",
    "digital service": "digital_experience",
    "staff attitude": "staff_service",
    "professionalism": "professional_service",
    "security": "safety_security",
    "food quality": "food_beverage",
    "product quality": "product_quality",
    "availability": "availability",
    "delivery": "delivery_fulfillment",
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
        taxonomy = Taxonomy(review["taxonomy"]) if review.get("taxonomy") else None
        return self._to_analysis(payload, review, taxonomy)

    @staticmethod
    def _to_analysis(payload: dict, review: dict, taxonomy: Taxonomy | None = None) -> dict:
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
        label = str(
            primary.get("complaint_taxonomy") or primary.get("taxonomy") or ""
        ).lower()
        if taxonomy is not None:
            # The pack's absa_map replaces the hard-coded hospital-era table.
            category = taxonomy.absa_map.get(label, taxonomy.fallback)
            fallback, praise = taxonomy.fallback, taxonomy.praise
        else:
            category = TAXONOMY_CATEGORIES.get(label, "other")
            fallback, praise = "other", "general_praise"
        if sentiment == "positive" and category == fallback:
            category = praise

        text = str(review.get("review_text") or "").lower()
        safety = any(
            word in text
            for word in (
                "salah obat",
                "malpraktik",
                "darurat",
                "nyawa",
                "infeksi",
                "cedera",
                "bahaya",
                "celaka",
                "kecelakaan",
                "keracunan",
                "kebakaran",
            )
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
            "negative": "Pelanggan menyampaikan keluhan yang memerlukan tindak lanjut.",
            "mixed": "Pelanggan memberi apresiasi sekaligus menyampaikan kendala.",
            "positive": "Pelanggan menyampaikan pengalaman pelayanan yang positif.",
        }
        keywords = list(
            dict.fromkeys(
                str(value)
                for item in aspects
                for value in (item.get("aspect"), item.get("opinion"))
                if value
            )
        )[:5]
        extra = {}
        if taxonomy is not None and taxonomy.tagging_enabled:
            # Every aspect ABSA found that the pack can name is a candidate tag.
            probabilities: dict[str, float] = {}
            for item in aspects:
                slug = taxonomy.absa_map.get(
                    str(item.get("complaint_taxonomy") or item.get("taxonomy") or "").lower()
                )
                if slug:
                    probabilities[slug] = max(
                        probabilities.get(slug, 0.0), float(item.get("confidence") or 0)
                    )
            extra["tags"] = taxonomy.pick_tags(probabilities)
        return {
            **extra,
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
            "is_safety_issue": safety,
            "absa": payload,
        }
