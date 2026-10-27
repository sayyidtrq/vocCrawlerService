"""Stateless v2 analysis and reply suggestion routes."""

from fastapi import APIRouter, Depends, Request

from app.config import get_settings
from app.services.stateless_ai_service import StatelessAiService
from apps.api.app_api.crawler_auth import require_crawler_token
from apps.api.app_api.integration_schemas import IntegrationErrorResponse
from apps.api.app_api.v2_ai_schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ReplySuggestionRequest,
    ReplySuggestionResponse,
)
from apps.api.app_api.v2_common import CrawlRoute, _envelope

router = APIRouter(
    prefix="/integration/v2", tags=["integration-v2-ai"],
    dependencies=[Depends(require_crawler_token)], route_class=CrawlRoute,
)
ERRORS = {code: {"model": IntegrationErrorResponse} for code in (400, 401, 429, 502, 503)}


def get_stateless_ai_service() -> StatelessAiService:
    return StatelessAiService(get_settings())


@router.post("/analysis", response_model=AnalysisResponse, responses=ERRORS)
def analyze(
    payload: AnalysisRequest, request: Request,
    service: StatelessAiService = Depends(get_stateless_ai_service),
) -> dict:
    return _envelope(request, service.analyze(payload.model_dump()))


@router.post("/reply-suggestion", response_model=ReplySuggestionResponse, responses=ERRORS)
def suggest_reply(
    payload: ReplySuggestionRequest, request: Request,
    service: StatelessAiService = Depends(get_stateless_ai_service),
) -> dict:
    return _envelope(request, service.suggest_reply(payload.model_dump()))
