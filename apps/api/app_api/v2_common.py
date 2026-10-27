"""Shared response handling for stateless v2 routes."""

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.services.integration_review_service import IntegrationRequestError
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse


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


def _envelope(request: Request, data: dict) -> dict:
    return {"data": data, "meta": {
        "api_version": API_VERSION,
        "request_id": request.headers.get("X-Request-ID") or str(uuid4()),
    }}
