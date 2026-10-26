from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.integrations.gemini_client import GeminiClientBase
from app.services.taxonomy_service import Taxonomy, tag_sentiment_of

logger = logging.getLogger(__name__)

TAG_SENTIMENT_CRITERIA = {
    "positive": "The review speaks well of this aspect.",
    "negative": "The review complains about or criticises this aspect.",
    "neutral": "The review mentions this aspect without praise or criticism.",
    "mixed": "The review both praises and criticises this aspect.",
}

# A request carries the core questions plus up to this many in total; extra tag
# questions go in further requests (fallback ladder of the multi-tagging plan).
MAX_QUESTIONS_PER_REQUEST = 40

TAXONOMY_CATEGORIES = {
    "professional service": "professional_service",
    "staff service": "staff_service",
    "registration": "administration",
    "waiting time": "waiting_time",
    "service speed": "waiting_time",
    "cleanliness": "cleanliness",
    "facilities": "facility",
    "parking": "parking",
    "price & value": "price_value",
    "billing & payment": "billing_payment",
    "availability": "availability",
    "delivery & fulfillment": "delivery_fulfillment",
    "customer service": "customer_service",
    "service quality": "service_quality",
    "booking & ordering": "booking_ordering",
    "digital experience": "digital_experience",
    "security & safety": "safety_security",
    "food & beverage": "food_beverage",
    "product quality": "product_quality",
}


SUMMARIES = {
    "negative": "Pelanggan menyampaikan keluhan yang memerlukan tindak lanjut.",
    "mixed": "Pelanggan memberi apresiasi sekaligus menyampaikan kendala.",
    "positive": "Pelanggan menyampaikan pengalaman pelayanan yang positif.",
}


class JevAiClient(GeminiClientBase):
    def __init__(
        self, settings: Settings, *, http_client: httpx.Client | None = None
    ) -> None:
        self.settings = settings
        self.model_name = settings.typesafe_model
        self.last_usage: dict[str, int] = {}
        headers = {}
        if settings.typesafe_api_key:
            headers["Authorization"] = f"Bearer {settings.typesafe_api_key}"
        self._http = http_client or httpx.Client(
            base_url=settings.typesafe_base_url.rstrip("/"),
            timeout=settings.typesafe_timeout_seconds,
            headers=headers,
        )

    def list_models(self) -> list[str]:
        response = self._http.get("/v1/models")
        if response.status_code >= 400:
            raise RuntimeError(
                f"TypeSafe returned HTTP {response.status_code}: {response.text}"
            )
        return [str(model["name"]) for model in response.json().get("models", [])]

    def _post(self, text: str, questions: dict) -> dict:
        response = self._http.post(
            "/v1/systemone",
            json={"state": text, "model": self.model_name, "questions": questions},
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"TypeSafe returned HTTP {response.status_code}: {response.text}"
            )
        return response.json()

    def _add_usage(self, usage: dict) -> None:
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        current = self.last_usage
        self.last_usage = {
            "prompt_tokens": current.get("prompt_tokens", 0) + input_tokens,
            "completion_tokens": current.get("completion_tokens", 0) + output_tokens,
            "total_tokens": current.get("total_tokens", 0) + input_tokens + output_tokens,
        }

    @staticmethod
    def _probability(answer: dict | None) -> float:
        answer = answer or {}
        try:
            return float(answer.get("noul", answer.get("probability", 0.0)))
        except (TypeError, ValueError):
            return 0.0

    def _ask(self, text: str, core: dict, extra: dict) -> dict:
        """Core questions first, then the extra (tag) ones in bounded chunks."""
        room = max(1, MAX_QUESTIONS_PER_REQUEST - len(core))
        keys = list(extra)
        chunks = [keys[i : i + room] for i in range(0, len(keys), room)] or [[]]
        self.last_usage = {}
        answers: dict = {}
        for index, chunk in enumerate(chunks):
            questions = {**(core if index == 0 else {}), **{k: extra[k] for k in chunk}}
            if not questions:
                continue
            payload = self._post(text, questions)
            self._add_usage(payload.get("usage", {}))
            answers.update(payload.get("answers", {}))
        return answers

    def _analyze_with_taxonomy(self, review: dict, taxonomy: Taxonomy) -> dict:
        text = review.get("review_text") or ""
        subject = f" of a {taxonomy.persona}" if taxonomy.persona else ""
        core = {
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
                "instructions": f"Which aspect is this review{subject} primarily about?",
                "criteria": {
                    slug: str(aspect.get("criteria") or slug)
                    for slug, aspect in taxonomy.aspects.items()
                },
            },
        }
        for flag in taxonomy.risk_flags:
            core[f"flag_{flag['slug']}"] = {"type": "noul", "instructions": flag["question"]}

        extra = {}
        if taxonomy.tagging_enabled:
            for slug, aspect in taxonomy.aspects.items():
                extra[f"tag_{slug}"] = {
                    "type": "noul",
                    "instructions": f"Does the review mention this aspect: {aspect.get('criteria') or slug}?",
                }

        answers = self._ask(text, core, extra)
        result = self._to_taxonomy_analysis(answers, review, taxonomy)
        if result.get("tags"):
            self._add_tag_sentiments(text, taxonomy, result)
        return result

    def _add_tag_sentiments(self, text: str, taxonomy: Taxonomy, result: dict) -> None:
        """What the review says about each tagged aspect: one more request, one choice per tag.

        An answer that is missing or invalid leaves the sentiment None; AnalysisService then
        gives the tag the review's own sentiment, so no tag ever leaves without one.
        """
        tags = result["tags"]
        questions = {
            f"sent_{tag['slug']}": {
                "type": "choice",
                "instructions": (
                    "What does the review say about this aspect: "
                    f"{taxonomy.aspects[tag['slug']].get('criteria') or tag['slug']}? "
                    "Judge only what is said about this aspect."
                ),
                "criteria": TAG_SENTIMENT_CRITERIA,
            }
            for tag in tags
        }
        payload = self._post(text, questions)
        self._add_usage(payload.get("usage", {}))
        answers = payload.get("answers", {})
        for tag in tags:
            tag["sentiment"] = tag_sentiment_of((answers.get(f"sent_{tag['slug']}") or {}).get("choice"))
        result["jev"] = {**result["jev"], **answers}

    def _to_taxonomy_analysis(self, answers: dict, review: dict, taxonomy: Taxonomy) -> dict:
        sentiment_ans = answers.get("sentiment", {})
        sentiment = str(sentiment_ans.get("choice", "unknown")).lower()
        category_ans = answers.get("category", {})
        category, _ = taxonomy.category(category_ans.get("choice") or taxonomy.fallback)
        if sentiment == "positive" and category == taxonomy.fallback:
            category = taxonomy.praise

        flags = {
            flag["slug"]: self._probability(answers.get(f"flag_{flag['slug']}")) > 0.5
            for flag in taxonomy.risk_flags
        }
        severities = {f["slug"]: f.get("severity") for f in taxonomy.risk_flags}
        rating = review.get("rating")
        urgency = (
            "critical"
            if any(on and severities[slug] == "critical" for slug, on in flags.items())
            else "high"
            if any(flags.values()) or (rating == 1 and sentiment == "negative")
            else "medium"
            if sentiment in {"negative", "mixed"}
            else "low"
        )

        result = {
            "sentiment": sentiment,
            "sentiment_score": float(sentiment_ans.get("confidence", 0.0)),
            "issue_category": category,
            "urgency": urgency,
            "summary": SUMMARIES.get(
                sentiment, "Ulasan belum memiliki aspek yang cukup meyakinkan."
            ),
            "recommended_action": (
                "Tinjau aspek layanan yang terdeteksi dan tindak lanjuti pola serupa."
            ),
            "keywords": [],
            "is_potential_viral": taxonomy.is_viral(flags),
            "is_safety_issue": taxonomy.is_safety(flags),
            "risk_flags": flags,
            "jev": answers,
        }
        if taxonomy.tagging_enabled:
            probabilities = {
                slug: self._probability(answers.get(f"tag_{slug}")) for slug in taxonomy.aspects
            }
            result["tags"] = taxonomy.add_primary(
                taxonomy.pick_tags(probabilities), category, round(float(category_ans.get("confidence", 0.0)), 4)
            )
        return result

    def suggest_reply(self, review_text: str, presets: list[dict], risk_flags: list[dict]) -> dict:
        """One request: which preset fits, the review language and the pack's risk flags.

        Jev only classifies (R8), so the answer is a preset id plus a confidence;
        the caller decides what to do with a low one.
        """
        questions = {
            "preset": {
                "type": "choice",
                "instructions": "Which prepared reply fits this review best?",
                "criteria": {p["id"]: str(p.get("when_to_use") or p["id"]) for p in presets},
            },
            "language": {
                "type": "choice",
                "instructions": "Which language is the review written in?",
                "criteria": {"id": "Indonesian", "en": "English"},
            },
        }
        for flag in risk_flags:
            questions[f"flag_{flag['slug']}"] = {"type": "noul", "instructions": flag["question"]}

        self.last_usage = {}
        payload = self._post(review_text, questions)
        self._add_usage(payload.get("usage", {}))
        answers = payload.get("answers", {})
        preset = answers.get("preset", {})
        return {
            "preset_id": str(preset.get("choice") or ""),
            "confidence": float(preset.get("confidence", 0.0) or 0.0),
            "language": "en" if str(answers.get("language", {}).get("choice")).lower() == "en" else "id",
            "risk_flags": {
                f["slug"]: self._probability(answers.get(f"flag_{f['slug']}")) > 0.5
                for f in risk_flags
            },
            "usage": dict(self.last_usage),
        }

    def analyze_review(self, review: dict) -> dict:
        if review.get("taxonomy"):
            return self._analyze_with_taxonomy(review, Taxonomy(review["taxonomy"]))

        text = review.get("review_text") or ""

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
                        "product quality": "Product quality, durability, condition, or performance",
                        "service quality": "Overall service quality and reliability",
                        "professional service": "Professional or specialist service and advice",
                        "staff service": "Staff attitude, responsiveness, friendliness, or courtesy",
                        "registration": "Registration, front desk, check-in, or administration",
                        "waiting time": "Waiting times, queues, service speed, delays",
                        "cleanliness": "Cleanliness of the premises, facility, or location",
                        "facilities": "Facilities, rooms, building, amenities",
                        "parking": "Parking area, vehicle access",
                        "price & value": "Price, cost, and value for money",
                        "billing & payment": "Invoices, billing, payments, or refunds",
                        "availability": "Stock, capacity, schedule, or service availability",
                        "delivery & fulfillment": "Delivery, fulfillment, pickup, or completion",
                        "customer service": "Customer support, helpdesk, or complaint handling",
                        "booking & ordering": "Booking, ordering, reservations, or checkout",
                        "digital experience": "Mobile app, website, portal, or other digital channel",
                        "security & safety": "Security, physical safety, danger, or incidents",
                        "food & beverage": "Food, beverages, meals, or catering",
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

        response = self._http.post(
            "/v1/systemone",
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"TypeSafe returned HTTP {response.status_code}: {response.text}"
            )

        result_payload = response.json()
        usage = result_payload.get("usage", {})
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = input_tokens + output_tokens
        self.last_usage = {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
        return self._to_analysis(result_payload, review)

    @staticmethod
    def _to_analysis(payload: dict, review: dict) -> dict:
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
            "is_safety_issue": safety,
            "jev": payload,
        }
