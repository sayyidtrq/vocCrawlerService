"""Reply suggestion for one review, for trusted OneBox service clients."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.services.integration_review_service import IntegrationRequestError
from app.services.reply_suggestion_service import (
    DEFAULT_PRESET_THRESHOLD,
    ReplySuggestionService,
)
from apps.api.app_api.integration_schemas import IntegrationErrorResponse
from apps.api.app_api.routers.integration_analysis import (
    ServicePrincipalDependency,
    SessionFactoryDependency,
    _authorize,
    _request_id,
    _require_entitlement,
    _response,
)

router = APIRouter(prefix="/integration/v1/reviews", tags=["integration-reply-suggestion"])


class PresetOffer(BaseModel):
    id: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    when_to_use: str = Field(min_length=1, max_length=300)


class Thresholds(BaseModel):
    preset: float = Field(default=DEFAULT_PRESET_THRESHOLD, ge=0, le=1)


class GeneratedOptions(BaseModel):
    # Stage 2: accepted so OneBox can send it now, ignored by v1.
    allowed: bool = False


class ReplySuggestionRequest(BaseModel):
    taxonomy_key: str | None = Field(default=None, max_length=80)
    presets: list[PresetOffer] = Field(max_length=30)
    thresholds: Thresholds = Thresholds()
    generated: GeneratedOptions = GeneratedOptions()


@router.post(
    "/{review_id}/reply-suggestion",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
        502: {"model": IntegrationErrorResponse},
    },
    summary="Suggest a prepared reply (preset id) for one review",
)
def reply_suggestion(
    review_id: int,
    payload: ReplySuggestionRequest,
    request: Request,
    principal: ServicePrincipalDependency,
    session_factory: SessionFactoryDependency,
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> dict:
    _authorize(principal)
    request_id = _request_id(request, x_request_id)
    _require_entitlement(principal.company_id, session_factory)
    try:
        result = ReplySuggestionService(
            company_id=principal.company_id, session_factory=session_factory
        ).suggest(
            review_id,
            [preset.model_dump() for preset in payload.presets],
            payload.taxonomy_key,
            payload.thresholds.preset,
        )
    except ValueError as exc:
        raise IntegrationRequestError(
            404, "REVIEW_NOT_FOUND", "Review was not found for this tenant."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - provider SDKs expose varied errors
        raise IntegrationRequestError(
            502, "SUGGESTION_FAILED", "The AI provider could not suggest a reply."
        ) from exc
    return _response(result, request_id)
