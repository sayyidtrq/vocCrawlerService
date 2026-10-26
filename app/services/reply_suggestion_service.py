"""Reply suggestion: Jev picks a preset id, this service decides what to do with it.

OneBox owns the preset text and sends only ``{id, when_to_use}`` (R4). Jev only
classifies, so everything else is a plain rule here: a numeric threshold, and a
safety gate driven by the pack's risk flags (R3). Generated text is stage 2.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Review
from app.db.session import get_session_factory
from app.integrations.analysis_client import create_analysis_client
from app.services.taxonomy_service import Taxonomy, load_taxonomies

logger = logging.getLogger(__name__)

DEFAULT_PRESET_THRESHOLD = 0.75


class ReplySuggestionService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: Any | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        self._client = client

    @property
    def client(self):
        # Only Jev can answer choice questions; resolved lazily so a missing key
        # does not break importing the service.
        if self._client is None:
            self._client = create_analysis_client(self.settings, "jev")
        return self._client

    def suggest(
        self,
        review_id: int,
        presets: list[dict],
        taxonomy_key: str | None,
        threshold: float = DEFAULT_PRESET_THRESHOLD,
    ) -> dict:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            review = session.scalar(statement)
            if review is None:
                raise ValueError("Review not found.")
            text = (review.review_text or "").strip()
            taxonomy = load_taxonomies(session, self.company_id, [taxonomy_key]).get(taxonomy_key)

        none = {"mode": "none", "tokens_used": 0}
        # Fail closed: without the pack's risk flags the safety gate cannot run,
        # so no preset is offered rather than one that might be unsafe.
        if taxonomy is None:
            return {**none, "reason": "taxonomy_unavailable"}
        if not text:
            return {**none, "reason": "no_text"}
        if not presets:
            return {**none, "reason": "no_presets"}

        answer = self.client.suggest_reply(text, presets, taxonomy.risk_flags)
        return decide(
            answer, taxonomy, presets, threshold, model=getattr(self.client, "model_name", None)
        )


def decide(
    answer: dict,
    taxonomy: Taxonomy,
    presets: list[dict],
    threshold: float = DEFAULT_PRESET_THRESHOLD,
    model: str | None = None,
) -> dict:
    """Jev's raw answer -> mode. Shared with scripts/eval_reply.py so both apply the same rules."""
    flags = taxonomy.flags(answer.get("risk_flags"))
    base = {
        "risk_flags": flags,
        "language": answer.get("language") or "id",
        "tokens_used": int((answer.get("usage") or {}).get("total_tokens") or 0),
        "model": model,
    }

    if taxonomy.is_safety(flags):
        return {"mode": "escalate", **base}

    preset_id = str(answer.get("preset_id") or "")
    confidence = float(answer.get("confidence") or 0.0)
    offered = {preset["id"] for preset in presets}
    if preset_id in offered and confidence >= threshold:
        return {"mode": "preset", "preset_id": preset_id, "confidence": round(confidence, 4), **base}
    # Below τ, or an id that was never offered: no guess, no generated text in v1.
    return {"mode": "none", "confidence": round(confidence, 4), **base}
