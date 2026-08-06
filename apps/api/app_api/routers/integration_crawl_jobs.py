"""Durable, non-blocking crawl queue contract for OneBox."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.db.session import get_session_factory
from app.services.crawl_job_service import CrawlJobService, CrawlQueueError
from app.services.integration_review_service import IntegrationRequestError
from apps.api.app_api.integration_crawl_schemas import (
    CrawlBatchCreateRequest,
    CrawlBatchListResponse,
    CrawlBatchResponse,
)
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal

router = APIRouter(prefix="/integration/v1/crawl-jobs", tags=["integration-crawl"])


def get_crawl_queue_session_factory():
    return get_session_factory()


def _require_scope(principal: ServicePrincipal, scope: str) -> None:
    if scope not in principal.scopes:
        raise IntegrationRequestError(
            403, "INSUFFICIENT_SCOPE", f"Token lacks the {scope} scope."
        )


def _request_id(request: Request, supplied: str | None) -> str:
    value = supplied or str(uuid4())
    request.state.request_id = value
    return value


def _translate_queue_error(exc: CrawlQueueError) -> IntegrationRequestError:
    return IntegrationRequestError(exc.status_code, exc.code, exc.message)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CrawlBatchResponse,
    responses={
        400: {"model": IntegrationErrorResponse},
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
        409: {"model": IntegrationErrorResponse},
    },
    summary="Queue tenant-scoped crawl jobs without waiting for Selenium",
)
def enqueue_crawl_jobs(
    payload: CrawlBatchCreateRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_crawl_queue_session_factory),
) -> dict:
    _require_scope(principal, "crawl:enqueue")
    request_id = _request_id(request, x_request_id)
    service = CrawlJobService(session_factory=session_factory)
    # Satu permintaan boleh memuat cabang dan kompetitor sekaligus. Keduanya
    # dipisah di sini supaya peta per-target di bawah tetap berkunci id cabang
    # dan tidak pernah bertabrakan dengan kompetitor yang tidak punya id itu.
    location_targets = [t for t in payload.targets if t.kind == "location"]
    competitor_targets = [t for t in payload.targets if t.kind == "competitor"]
    try:
        batch, _created = service.enqueue(
            company_id=principal.company_id,
            client_id=principal.client_id,
            idempotency_key=idempotency_key,
            onebox_location_ids=[
                target.onebox_location_id for target in location_targets
            ],
            target_review_counts={
                target.onebox_location_id: target.target_review_count
                for target in location_targets
                if target.target_review_count is not None
            },
            target_date_ranges={
                target.onebox_location_id: (target.date_from, target.date_to)
                for target in location_targets
                if target.date_from is not None or target.date_to is not None
            },
            target_sorts={
                target.onebox_location_id: target.sort_by
                for target in location_targets
                if target.sort_by and target.sort_by != "newest"
            },
            competitor_targets=[
                {
                    "external_place_id": (target.external_place_id or "").strip(),
                    "target_review_count": target.target_review_count,
                    "date_from": target.date_from,
                    "date_to": target.date_to,
                    "sort_by": target.sort_by,
                }
                for target in competitor_targets
            ],
            slot=payload.slot,
        )
    except CrawlQueueError as exc:
        raise _translate_queue_error(exc) from exc
    return {
        "data": batch,
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }


@router.get(
    "",
    response_model=CrawlBatchListResponse,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
    },
    summary="List recent crawl batches for the service token tenant",
)
def list_crawl_batches(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_crawl_queue_session_factory),
) -> dict:
    _require_scope(principal, "crawl:read")
    request_id = _request_id(request, x_request_id)
    data = CrawlJobService(session_factory=session_factory).list_batches(
        company_id=principal.company_id, limit=limit
    )
    return {
        "data": data,
        "meta": {"api_version": API_VERSION, "request_id": request_id, "limit": limit},
    }


@router.get(
    "/{batch_id}",
    response_model=CrawlBatchResponse,
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
    },
    summary="Read crawl batch status and per-target results",
)
def get_crawl_batch(
    batch_id: str,
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_crawl_queue_session_factory),
) -> dict:
    _require_scope(principal, "crawl:read")
    request_id = _request_id(request, x_request_id)
    try:
        batch = CrawlJobService(session_factory=session_factory).get_batch(
            company_id=principal.company_id, public_id=batch_id
        )
    except CrawlQueueError as exc:
        raise _translate_queue_error(exc) from exc
    return {
        "data": batch,
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }
