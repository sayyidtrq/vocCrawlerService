"""Stateless v2 crawl routes."""

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.config import get_settings
from app.services.integration_review_service import IntegrationRequestError
from app.services.stateless_crawl_service import StatelessCrawlService
from apps.api.app_api.crawler_auth import require_crawler_token
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse
from apps.api.app_api.v2_crawl_schemas import CrawlPageResponse, CrawlRequest, CrawlStartResponse


class CrawlRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except IntegrationRequestError as exc:
                headers = {}
                if exc.status_code == 401:
                    headers["WWW-Authenticate"] = "Bearer"
                if exc.status_code == 429:
                    headers["Retry-After"] = "60"
                error = IntegrationErrorResponse(error={
                    "code": exc.code, "message": exc.message,
                    "request_id": request.headers.get("X-Request-ID") or str(uuid4()),
                })
                return JSONResponse(status_code=exc.status_code, content=error.model_dump(), headers=headers)

        return handle


router = APIRouter(
    prefix="/integration/v2/crawls", tags=["integration-v2-crawls"],
    dependencies=[Depends(require_crawler_token)], route_class=CrawlRoute,
)
ERRORS = {code: {"model": IntegrationErrorResponse} for code in (400, 401, 404, 429, 502, 503)}


def get_stateless_crawl_service() -> StatelessCrawlService:
    return StatelessCrawlService(get_settings())


def _envelope(request: Request, data: dict) -> dict:
    return {"data": data, "meta": {
        "api_version": API_VERSION,
        "request_id": request.headers.get("X-Request-ID") or str(uuid4()),
    }}


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
