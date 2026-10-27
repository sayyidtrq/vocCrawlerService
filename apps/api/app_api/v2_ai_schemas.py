"""Stateless analysis and reply suggestion contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.reply_suggestion_service import DEFAULT_PRESET_THRESHOLD
from apps.api.app_api.integration_schemas import IntegrationMeta

Provider = Literal["jev", "openai", "absa"]


class AnalysisReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    review_hash: str | None = Field(default=None, min_length=1, max_length=255)
    rating: int | None = Field(default=None, ge=1, le=5, strict=True)
    text: str = Field(max_length=10000)
    reviewer_name: str | None = Field(default=None, max_length=255)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_id: int = Field(default=0, ge=0, strict=True)
    provider: Provider | None = None
    taxonomy: dict[str, Any] | None = None
    taxonomy_key: str | None = Field(default=None, min_length=1, max_length=80)
    reviews: list[AnalysisReview] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_review_ids(self) -> AnalysisRequest:
        if len({review.id for review in self.reviews}) != len(self.reviews):
            raise ValueError("Duplicate review ids are not allowed.")
        return self


class PresetOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    when_to_use: str = Field(min_length=1, max_length=300)


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: float = Field(default=DEFAULT_PRESET_THRESHOLD, ge=0, le=1)


class GeneratedOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool = False


class ReplySuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site_id: int = Field(default=0, ge=0, strict=True)
    review_hash: str | None = Field(default=None, max_length=255)
    text: str = Field(max_length=10000)
    taxonomy: dict[str, Any]
    taxonomy_key: str | None = Field(default=None, min_length=1, max_length=80)
    presets: list[PresetOffer] = Field(max_length=30)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    generated: GeneratedOptions = Field(default_factory=GeneratedOptions)


class AnalysisError(BaseModel):
    code: str
    message: str


class AnalysisResult(BaseModel):
    id: str
    review_hash: str | None
    status: Literal["analyzed", "rating_fallback", "failed"]
    corrected: bool
    analysis: dict[str, Any] | None = Field(description="Free-form cleaned analysis fields; never raw provider output.")
    error: AnalysisError | None


class AnalysisSummary(BaseModel):
    analyzed: int
    rating_fallback: int
    failed: int


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AnalysisData(BaseModel):
    provider: Provider
    model: str | None
    summary: AnalysisSummary
    usage: TokenUsage
    results: list[AnalysisResult]


class AnalysisResponse(BaseModel):
    data: AnalysisData
    meta: IntegrationMeta


class ReplySuggestionResponse(BaseModel):
    data: dict[str, Any] = Field(description="Reply decision fields, exactly as emitted by the v1 decision rules.")
    meta: IntegrationMeta
