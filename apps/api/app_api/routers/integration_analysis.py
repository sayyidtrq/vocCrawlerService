"""Tenant-scoped AI analysis actions for trusted OneBox service clients."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Location
from app.db.session import get_session_factory
from app.integrations.local_llm_client import LocalLLMClient
from app.services.analysis_service import AnalysisService
from app.services.entitlement_service import EntitlementError, EntitlementService
from app.services.integration_review_service import IntegrationRequestError
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse
from apps.api.app_api.serializers import to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal

router = APIRouter(
    prefix="/integration/v1/analysis", tags=["integration-analysis"]
)
REQUIRED_SCOPE = "analysis:write"


class IntegrationAnalyzeRequest(BaseModel):
    location_id: int | None = Field(default=None, ge=1)
    rating: int | None = Field(default=None, ge=1, le=5)


class IntegrationRollbackRequest(BaseModel):
    model_name: str = Field(min_length=1)
    since: datetime | None = None


def get_integration_analysis_session_factory():
    """Test seam; production uses the normal application database."""

    return get_session_factory()


ServicePrincipalDependency = Annotated[
    ServicePrincipal, Depends(require_service_principal)
]
SessionFactoryDependency = Annotated[
    object, Depends(get_integration_analysis_session_factory)
]


def _authorize(principal: ServicePrincipal) -> None:
    if REQUIRED_SCOPE not in principal.scopes:
        raise IntegrationRequestError(
            403,
            "INSUFFICIENT_SCOPE",
            f"Token lacks the {REQUIRED_SCOPE} scope.",
        )


def _request_id(request: Request, supplied: str | None) -> str:
    value = supplied or str(uuid4())
    request.state.request_id = value
    return value


def _require_entitlement(company_id: int, session_factory) -> None:
    try:
        EntitlementService(
            company_id=company_id, session_factory=session_factory
        ).require_ai_enabled()
    except EntitlementError as exc:
        raise IntegrationRequestError(403, "AI_NOT_ENABLED", str(exc)) from exc


def _require_location(company_id: int, location_id: int, session_factory) -> None:
    with session_factory() as session:
        exists_for_tenant = session.scalar(
            select(Location.id).where(
                Location.id == location_id,
                Location.company_id == company_id,
            )
        )
    if exists_for_tenant is None:
        raise IntegrationRequestError(
            404, "LOCATION_NOT_FOUND", "Location was not found for this tenant."
        )


def _response(data: dict, request_id: str) -> dict:
    return {
        "data": to_jsonable(data),
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }


def _raise_if_single_review_failed(result: dict) -> None:
    """A rerun is synchronous; HTTP success must mean the review succeeded."""

    if int(result.get("failed") or 0) <= 0:
        return
    raise IntegrationRequestError(
        502,
        "ANALYSIS_FAILED",
        "The AI provider could not analyze this review after retries.",
    )


@router.get(
    "/models",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        502: {"model": IntegrationErrorResponse},
    },
    summary="List AI models available in this Crawler deployment",
)
def available_models(
    request: Request,
    principal: ServicePrincipalDependency,
    session_factory: SessionFactoryDependency,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict:
    _authorize(principal)
    request_id = _request_id(request, x_request_id)
    _require_entitlement(principal.company_id, session_factory)
    settings = get_settings()
    try:
        models = LocalLLMClient(settings).list_models()
    except Exception as exc:  # noqa: BLE001 - provider SDKs expose varied errors
        raise IntegrationRequestError(
            502,
            "MODEL_DISCOVERY_FAILED",
            "The configured AI provider did not return its model list.",
        ) from exc
    return _response(
        {"models": models, "default_model": settings.local_llm_model},
        request_id,
    )


@router.post(
    "/pending",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
    },
    summary="Run pending AI analysis for the service-token tenant",
)
def analyze_pending(
    payload: IntegrationAnalyzeRequest,
    request: Request,
    principal: ServicePrincipalDependency,
    session_factory: SessionFactoryDependency,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict:
    _authorize(principal)
    request_id = _request_id(request, x_request_id)
    _require_entitlement(principal.company_id, session_factory)
    if payload.location_id is not None:
        _require_location(principal.company_id, payload.location_id, session_factory)
    result = AnalysisService(
        company_id=principal.company_id, session_factory=session_factory
    ).analyze_pending(location_id=payload.location_id, rating=payload.rating)
    return _response(result, request_id)


@router.post(
    "/reviews/{review_id}/rerun",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
    },
    summary="Rerun one review analysis for the service-token tenant",
)
def rerun_review(
    review_id: int,
    request: Request,
    principal: ServicePrincipalDependency,
    session_factory: SessionFactoryDependency,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict:
    _authorize(principal)
    request_id = _request_id(request, x_request_id)
    _require_entitlement(principal.company_id, session_factory)
    try:
        result = AnalysisService(
            company_id=principal.company_id, session_factory=session_factory
        ).rerun_review(review_id)
    except ValueError as exc:
        raise IntegrationRequestError(
            404, "REVIEW_NOT_FOUND", "Review was not found for this tenant."
        ) from exc
    _raise_if_single_review_failed(result)
    return _response(result, request_id)


@router.post(
    "/rollback",
    responses={
        400: {"model": IntegrationErrorResponse},
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
    },
    summary="Rollback analyses produced by one model for this tenant",
)
def rollback_analyses(
    payload: IntegrationRollbackRequest,
    request: Request,
    principal: ServicePrincipalDependency,
    session_factory: SessionFactoryDependency,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict:
    _authorize(principal)
    request_id = _request_id(request, x_request_id)
    try:
        result = AnalysisService(
            company_id=principal.company_id, session_factory=session_factory
        ).rollback_analyses(model_name=payload.model_name, since=payload.since)
    except ValueError as exc:
        raise IntegrationRequestError(400, "INVALID_PARAMETER", str(exc)) from exc
    return _response(result, request_id)


@router.get(
    "/quality-summary",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
    },
    summary="Read recent AI quality status for the service-token tenant",
)
def quality_summary(
    request: Request,
    principal: ServicePrincipalDependency,
    session_factory: SessionFactoryDependency,
    hours: int = 24,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict:
    _authorize(principal)
    request_id = _request_id(request, x_request_id)
    try:
        result = AnalysisService(
            company_id=principal.company_id, session_factory=session_factory
        ).quality_summary(hours=hours)
    except ValueError as exc:
        raise IntegrationRequestError(400, "INVALID_PARAMETER", str(exc)) from exc
    return _response(result, request_id)
