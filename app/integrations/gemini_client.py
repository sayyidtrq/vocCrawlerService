from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewAnalysisResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative", "mixed", "unknown"]
    sentiment_score: float = Field(ge=0, le=1)
    # Free text here: the allowed values depend on the location's taxonomy and
    # are enforced by AnalysisService against OneBox's snapshot.
    issue_category: str
    urgency: Literal["low", "medium", "high", "critical", "unknown"]
    summary: str
    recommended_action: str
    keywords: list[str]
    is_potential_viral: bool
    is_safety_issue: bool
    # Only filled when the review was analysed under an OneBox taxonomy.
    risk_flags: dict[str, bool] | None = None
    tags: list[Any] | None = None


class GeminiClientBase(ABC):
    model_name: str

    @abstractmethod
    def analyze_review(self, review: dict) -> dict:
        raise NotImplementedError
