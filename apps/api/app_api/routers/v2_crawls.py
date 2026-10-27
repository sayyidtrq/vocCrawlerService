"""Stateless v2 crawl routes."""

from fastapi import APIRouter, Depends, Header, Query, Request

from app.config import get_settings
from app.services.stateless_crawl_service import StatelessCrawlService
from apps.api.app_api.crawler_auth import require_crawler_token
from apps.api.app_api.integration_schemas import IntegrationErrorResponse
from apps.api.app_api.v2_common import CrawlRoute, _envelope
from apps.api.app_api.v2_crawl_schemas import CrawlPageResponse, CrawlRequest, CrawlStartResponse


router = APIRouter(
    prefix="/integration/v2/crawls", tags=["integration-v2-crawls"],
    dependencies=[Depends(require_crawler_token)], route_class=CrawlRoute,
)
ERRORS = {code: {"model": IntegrationErrorResponse} for code in (400, 401, 404, 429, 502, 503)}
ERRORS[503]["description"] = "V2_NOT_CONFIGURED, APIFY_NOT_CONFIGURED, or APIFY_ACCOUNTS_EXHAUSTED."


def get_stateless_crawl_service() -> StatelessCrawlService:
    return StatelessCrawlService(get_settings())


@router.post("", status_code=202, response_model=CrawlStartResponse, responses=ERRORS)
def start_crawls(
    payload: CrawlRequest, request: Request,
    idempotency_key: str | None = Header(default=None, min_length=8, max_length=128),
    service: StatelessCrawlService = Depends(get_stateless_crawl_service),
) -> dict:
    return _envelope(request, service.start_crawls(payload.model_dump(mode="json"), idempotency_key))


@router.get("/{crawl_id}", response_model=CrawlPageResponse, responses=ERRORS)
def get_crawl(
    crawl_id: str, request: Request, cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: StatelessCrawlService = Depends(get_stateless_crawl_service),
) -> dict:
    return _envelope(request, service.get_crawl(crawl_id, cursor=cursor, limit=limit))
