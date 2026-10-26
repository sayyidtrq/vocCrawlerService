from __future__ import annotations

import json
from pathlib import Path

from openai import APIError, OpenAI

from app.config import Settings
from app.integrations.gemini_client import GeminiClientBase, ReviewAnalysisResult
from app.services.taxonomy_service import Taxonomy

ALLOWED_ISSUE_CATEGORIES = {
    "product_quality",
    "service_quality",
    "professional_service",
    "staff_service",
    "administration",
    "waiting_time",
    "cleanliness",
    "facility",
    "parking",
    "accessibility",
    "price_value",
    "billing_payment",
    "availability",
    "delivery_fulfillment",
    "customer_service",
    "booking_ordering",
    "digital_experience",
    "safety_security",
    "food_beverage",
    "general_praise",
    "other",
}
ISSUE_CATEGORY_ALIASES = {
    "waiting_room": "waiting_time",
    "doctor_service": "professional_service",
    "nurse_service": "staff_service",
    "billing": "billing_payment",
    "pharmacy": "availability",
    "emergency_room": "safety_security",
    "inpatient": "facility",
    "booking_system": "booking_ordering",
    "staff_communication": "staff_service",
    "security": "safety_security",
    "food": "food_beverage",
    "patient_experience": "service_quality",
}


class LLMProviderError(RuntimeError):
    """An analysis provider request failed before producing a response."""


def _coerce_model_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return False


def _normalize_model_output(parsed: dict, taxonomy: Taxonomy | None = None) -> dict:
    normalized = dict(parsed)
    if taxonomy is not None:
        normalized["issue_category"] = taxonomy.category(
            normalized.get("issue_category") or taxonomy.fallback
        )[0]
    else:
        category = str(normalized.get("issue_category") or "other").strip().lower()
        category = ISSUE_CATEGORY_ALIASES.get(category, category)
        normalized["issue_category"] = (
            category if category in ALLOWED_ISSUE_CATEGORIES else "other"
        )
    if "is_safety_issue" not in normalized:
        normalized["is_safety_issue"] = normalized.get("is_patient_safety_issue")
    for field in ("is_potential_viral", "is_safety_issue"):
        normalized[field] = _coerce_model_bool(normalized.get(field))
    return normalized


def _build_example_from_schema(schema: dict) -> dict:
    """Bangun contoh instance JSON (bukan schema) dari pydantic JSON schema,
    supaya kalau field di ReviewAnalysisResult berubah, contoh di prompt ikut update."""
    example: dict = {}
    properties = schema.get("properties", {})
    # Optional fields (risk_flags, tags) belong to the taxonomy instructions, not the example.
    for field in schema.get("required", list(properties)):
        spec = properties[field]
        if "enum" in spec:
            example[field] = spec["enum"][0]
        elif spec.get("type") == "string":
            example[field] = "contoh teks singkat"
        elif spec.get("type") == "integer":
            example[field] = 1
        elif spec.get("type") == "number":
            example[field] = 1.0
        elif spec.get("type") == "boolean":
            example[field] = False
        elif spec.get("type") == "array":
            example[field] = ["contoh"]
        else:
            example[field] = None
    return example


class LocalLLMClient(GeminiClientBase):
    def __init__(
        self,
        settings: Settings,
        sdk_client: OpenAI | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        self.settings = settings
        self.model_name = model_name or settings.local_llm_model
        self.last_usage: dict[str, int] = {}

        self.client = sdk_client or OpenAI(
            base_url=base_url or self.settings.local_llm_base_url,
            api_key=api_key or self.settings.local_llm_api_key or "ollama",
        )

        prompt_path = (
            Path(__file__).resolve().parent.parent
            / "prompts"
            / "review_analysis_prompt.md"
        )
        self.system_instruction = prompt_path.read_text(encoding="utf-8")

        # Enforce JSON output for local LLMs — kirim CONTOH INSTANCE, bukan JSON Schema mentah,
        # supaya model tidak ikut meniru struktur "properties/required/title/type".
        schema = ReviewAnalysisResult.model_json_schema()
        example = _build_example_from_schema(schema)

        self.system_instruction += (
            "\n\nIMPORTANT: You must return ONLY raw JSON with exactly these top-level keys, "
            "filled with your real analysis of the review. "
            "Do NOT return a JSON Schema definition — do NOT include keys such as "
            "'properties', 'required', 'title', 'type', or 'description' anywhere in your output. "
            "Your entire response must be a single flat JSON object shaped exactly like this example "
            "(the values below are placeholders only, replace them with your actual analysis):\n\n"
            f"{json.dumps(example, indent=2, ensure_ascii=False)}\n\n"
            "Do not include markdown code blocks, explanations, or any other text."
        )

    def list_models(self) -> list[str]:
        """Return model IDs exposed by the configured OpenAI-compatible server.

        Model availability belongs to the deployment, not the source tree.  In
        particular Ollama model IDs include tags (for example ``name:tag``), so
        keeping a second hardcoded list in OneBox is both brittle and prone to
        subtle spelling errors.  This method is intentionally small so it also
        works with other OpenAI-compatible providers that implement
        ``GET /v1/models``.
        """

        response = self.client.models.list()
        models = {
            str(getattr(item, "id", "") or "").strip()
            for item in getattr(response, "data", [])
        }
        return sorted(model for model in models if model)

    @staticmethod
    def _taxonomy_instruction(taxonomy: Taxonomy) -> str:
        """Closed vocabulary for one location; replaces the generic category guidance."""
        lines = [
            "\n\nTAXONOMY OVERRIDE (this location's own vocabulary; it replaces the generic "
            "category guidance above, including `general_praise` and `other`):",
        ]
        if taxonomy.persona:
            lines.append(f"The review is from a {taxonomy.persona}.")
        lines.append("`issue_category` MUST be exactly one of these slugs:")
        lines += [
            f"- {slug}: {aspect.get('criteria') or slug}" for slug, aspect in taxonomy.aspects.items()
        ]
        lines.append(
            f"Use `{taxonomy.praise}` for general praise without a specific issue and "
            f"`{taxonomy.fallback}` when nothing else fits."
        )
        if taxonomy.risk_flags:
            lines.append(
                "Also add `risk_flags`: an object with a true/false value for EACH of these keys:"
            )
            lines += [f"- {flag['slug']}: {flag['question']}" for flag in taxonomy.risk_flags]
        if taxonomy.tagging_enabled:
            lines.append(
                f"Also add `tags`: a JSON array with one object for EVERY aspect above the review "
                f"mentions (at most {taxonomy.max_tags}), most prominent first. Each object is "
                '{"slug": <aspect slug>, "sentiment": <positive|negative|neutral|mixed>}, where '
                "sentiment is what the review says about THAT aspect only (a review can praise one "
                "aspect and criticise another)."
            )
        return "\n".join(lines)

    def analyze_review(self, review: dict) -> dict:
        taxonomy = Taxonomy(review["taxonomy"]) if review.get("taxonomy") else None
        system_instruction = self.system_instruction
        if taxonomy is not None:
            system_instruction += self._taxonomy_instruction(taxonomy)
        prompt = (
            "Analisis review berikut sesuai instruksi sistem.\n\n"
            f"Rating: {review.get('rating')}\n"
            f"Reviewer: {review.get('reviewer_name') or 'Anonymous'}\n"
            f"Waktu review: {review.get('review_time') or 'unknown'}\n"
            f"Teks review:\n{review.get('review_text') or ''}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=1000,
            )
        except APIError as exc:
            raise LLMProviderError(f"OpenAI API request failed: {exc}") from exc

        usage = getattr(response, "usage", None)
        self.last_usage = {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Local LLM returned an empty response.")

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Local LLM returned invalid JSON.\nRaw response: {content}"
            ) from exc

        # Defensive fallback: kalau model tetap salah balikin bentuk JSON Schema
        # (ada 'properties' tapi field asli seperti 'sentiment' tidak ada di top-level),
        # ambil isinya dari dalam 'properties' supaya tidak langsung gagal total.
        if "properties" in parsed and "sentiment" not in parsed:
            parsed = parsed["properties"]

        parsed = _normalize_model_output(parsed, taxonomy)
        try:
            return ReviewAnalysisResult.model_validate(parsed).model_dump()
        except ValueError as exc:
            raise RuntimeError(
                f"Local LLM returned a response that does not match the analysis schema.\nRaw response: {content}"
            ) from exc
