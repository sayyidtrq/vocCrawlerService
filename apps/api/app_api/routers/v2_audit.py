"""Read-only v2 audit routes."""

from fastapi import APIRouter, Depends, Query, Request

from app.services.audit_query_service import AuditQueryService
from apps.api.app_api.crawler_auth import require_crawler_token
from apps.api.app_api.integration_schemas import IntegrationErrorResponse
from apps.api.app_api.v2_audit_schemas import AuditSummaryResponse, ReconcileRequest, ReconcileResponse
from apps.api.app_api.v2_common import CrawlRoute, _envelope

router = APIRouter(
    prefix="/integration/v2/audit", tags=["integration-v2-audit"],
    dependencies=[Depends(require_crawler_token)], route_class=CrawlRoute,
)
ERRORS = {code: {"model": IntegrationErrorResponse} for code in (400, 401, 503)}


def get_audit_query_service() -> AuditQueryService:
    return AuditQueryService()


@router.get("/summary", response_model=AuditSummaryResponse, responses=ERRORS)
def summary(
    request: Request, site_id: int = Query(default=0, ge=0),
    place_id: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    service: AuditQueryService = Depends(get_audit_query_service),
) -> dict:
    return _envelope(request, service.summary(site_id=site_id, place_id=place_id, limit=limit))


@router.post("/reconcile", response_model=ReconcileResponse, responses=ERRORS)
def reconcile(
    payload: ReconcileRequest, request: Request,
    service: AuditQueryService = Depends(get_audit_query_service),
) -> dict:
    return _envelope(request, service.reconcile(payload.model_dump()))
