from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.services.integration_review_service import IntegrationRequestError
from apps.api.app_api.errors import register_exception_handlers
from apps.api.app_api.routers import (
    analysis,
    dashboard,
    exports,
    fetch_jobs,
    fetch_logs,
    health,
    integration_reviews,
    integration_crawl_jobs,
    integration_competitor_reviews,
    locations,
    pipeline,
    reviews,
    settings,
    auth,
    places,
    competitors,
)

INTEGRATION_PREFIX = "/api/integration/"


def _integration_error(request: Request, status_code: int, code: str, message: str):
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or str(uuid4())
    )
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )


def register_integration_exception_handlers(app: FastAPI) -> None:
    """Error envelope for the v1 contract.

    The envelope in errors.py has no request_id, and OneBox needs one to correlate
    a failed pull with our logs. Rather than reshape the FE's envelope, these
    handlers apply only under /api/integration/ and hand every other path straight
    back to the existing behaviour.
    """

    @app.exception_handler(IntegrationRequestError)
    async def integration_request_error_handler(
        request: Request, exc: IntegrationRequestError
    ) -> JSONResponse:
        return _integration_error(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # The contract answers 400 for a bad parameter; FastAPI's default is 422.
        # Only the integration routes are remapped — FE clients keep seeing 422.
        if not request.url.path.startswith(INTEGRATION_PREFIX):
            return await request_validation_exception_handler(request, exc)
        return _integration_error(
            request, 400, "INVALID_PARAMETER", "Request parameters are invalid."
        )


def _drop_advertised_422_from_integration_paths(app: FastAPI) -> None:
    """Stop OpenAPI promising a 422 the integration routes never return.

    FastAPI adds a 422 to any route with validated parameters, but
    validation_error_handler answers 400 under /api/integration/. Leaving the 422
    in the published schema would have OneBox code a branch that can never fire.
    """
    base_openapi = app.openapi

    def openapi() -> dict:
        schema = base_openapi()
        for path, operations in schema.get("paths", {}).items():
            if not path.startswith(INTEGRATION_PREFIX):
                continue
            for operation in operations.values():
                operation.get("responses", {}).pop("422", None)
        return schema

    app.openapi = openapi


def create_app() -> FastAPI:
    app = FastAPI(
        title="Review System API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_settings().cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    register_integration_exception_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(places.router, prefix="/api")
    app.include_router(competitors.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(locations.router, prefix="/api")
    app.include_router(reviews.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(fetch_jobs.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    app.include_router(exports.router, prefix="/api")
    app.include_router(pipeline.router, prefix="/api")
    app.include_router(fetch_logs.router, prefix="/api")
    app.include_router(integration_reviews.router, prefix="/api")
    app.include_router(integration_crawl_jobs.router, prefix="/api")
    app.include_router(integration_competitor_reviews.router, prefix="/api")
    _drop_advertised_422_from_integration_paths(app)
    return app


app = create_app()
