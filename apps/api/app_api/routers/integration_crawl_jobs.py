"""Durable, non-blocking crawl queue contract for OneBox."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.config import get_settings
from app.db.session import get_session_factory
from app.services.crawl_queue import CrawlQueue, CrawlQueueError
from app.services.integration_review_service import IntegrationRequestError
from app.services.review_count_probe import ReviewCountProbe, ReviewTargetNotFound
from apps.api.app_api.integration_crawl_schemas import (
    CrawlBatchCreateRequest,
    CrawlBatchListResponse,
    CrawlBatchResponse,
    CrawlTargetRequest,
)
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal

router = APIRouter(prefix="/integration/v1/crawl-jobs", tags=["integration-crawl"])
logger = logging.getLogger(__name__)

_COVERAGE_TO_CRAWL_MODE = {
    "full_backfill": "initial_backfill",
    "date_window": "custom_range",
    "delta": "regular_delta",
}
_CRAWL_MODE_TO_COVERAGE = {value: key for key, value in _COVERAGE_TO_CRAWL_MODE.items()}


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


def _target_date_range(payload: CrawlBatchCreateRequest, target: CrawlTargetRequest):
    if target.date_from is not None or target.date_to is not None:
        return target.date_from, target.date_to
    if payload.date_range is not None:
        return payload.date_range.from_, payload.date_range.to
    return None, None


def _target_crawl_options(
    payload: CrawlBatchCreateRequest, target: CrawlTargetRequest
) -> dict:
    date_from, date_to = _target_date_range(payload, target)
    crawl_mode = target.crawl_mode or payload.crawl_mode
    coverage = target.coverage or _CRAWL_MODE_TO_COVERAGE.get(
        crawl_mode, "date_window" if date_from or date_to else "delta"
    )
    legacy_budget = target.effective_review_limit or payload.max_reviews_to_collect
    if coverage == "date_window":
        if target.budget is not None:
            raise CrawlQueueError(
                400, "INVALID_PARAMETER", "budget is not allowed for date_window coverage."
            )
        if date_from is None and date_to is None:
            raise CrawlQueueError(
                400,
                "INVALID_PARAMETER",
                "date_window coverage requires date_from or date_to.",
            )
        if legacy_budget is not None:
            logger.info("Ignoring legacy review limit for date_window coverage.")
        budget = None
    else:
        budget = target.budget or legacy_budget
    if coverage == "full_backfill" and (date_from is not None or date_to is not None):
        raise CrawlQueueError(
            400,
            "INVALID_PARAMETER",
            "full_backfill coverage does not accept date bounds.",
        )
    # crawl_mode lama tetap disimpan untuk pembaca lama, tapi harus sejalan
    # dengan coverage; coverage eksplisit yang menang.
    if target.coverage or not crawl_mode:
        crawl_mode = _COVERAGE_TO_CRAWL_MODE[coverage]
    return {
        "coverage": coverage,
        "budget": budget,
        "crawl_mode": crawl_mode,
        "max_reviews_to_collect": budget,
        "scan_limit": target.scan_limit or payload.scan_limit,
        "review_quota_remaining": payload.review_quota_remaining,
        "dry_run": payload.dry_run,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": target.sort_by,
    }


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
    summary="Queue tenant-scoped Apify crawl jobs",
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
    service = CrawlQueue(session_factory=session_factory)
    # Satu permintaan boleh memuat cabang dan kompetitor sekaligus. Keduanya
    # dipisah di sini supaya peta per-target di bawah tetap berkunci id cabang
    # dan tidak pernah bertabrakan dengan kompetitor yang tidak punya id itu.
    location_targets = [t for t in payload.targets if t.kind == "location"]
    competitor_targets = [t for t in payload.targets if t.kind == "competitor"]
    try:
        location_options = {
            target.onebox_location_id: _target_crawl_options(payload, target)
            for target in location_targets
        }
        competitor_options = {
            (target.external_place_id or "").strip(): _target_crawl_options(
                payload, target
            )
            for target in competitor_targets
        }
        batch, _created = service.enqueue(
            company_id=principal.company_id,
            client_id=principal.client_id,
            idempotency_key=idempotency_key,
            onebox_location_ids=[
                target.onebox_location_id for target in location_targets
            ],
            target_review_counts={
                target.onebox_location_id: location_options[
                    target.onebox_location_id
                ]["budget"]
                for target in location_targets
                if location_options[target.onebox_location_id]["budget"] is not None
            },
            target_date_ranges={
                target.onebox_location_id: _target_date_range(payload, target)
                for target in location_targets
                if (
                    target.date_from is not None
                    or target.date_to is not None
                    or payload.date_range is not None
                )
            },
            target_sorts={
                target.onebox_location_id: target.sort_by
                for target in location_targets
                if target.sort_by and target.sort_by != "newest"
            },
            target_crawl_options=location_options,
            competitor_targets=[
                {
                    "external_place_id": (target.external_place_id or "").strip(),
                    "target_review_count": competitor_options[
                        (target.external_place_id or "").strip()
                    ]["budget"],
                    "date_from": _target_date_range(payload, target)[0],
                    "date_to": _target_date_range(payload, target)[1],
                    "sort_by": target.sort_by,
                    **competitor_options[(target.external_place_id or "").strip()],
                    "dry_run": payload.dry_run,
                }
                for target in competitor_targets
            ],
            slot=payload.slot,
        )
    except CrawlQueueError as exc:
        raise _translate_queue_error(exc) from exc
    return {
        "data": {**batch, "reused_existing_job": not _created},
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
    data = CrawlQueue(session_factory=session_factory).list_batches(
        company_id=principal.company_id, limit=limit
    )
    return {
        "data": data,
        "meta": {"api_version": API_VERSION, "request_id": request_id, "limit": limit},
    }


def _probe_service(session_factory) -> ReviewCountProbe:
    return ReviewCountProbe(session_factory, get_settings())


def _target_not_found(onebox_location_id: int) -> IntegrationRequestError:
    return IntegrationRequestError(
        404,
        "TARGET_NOT_FOUND",
        f"Location {onebox_location_id} is absent or outside this tenant.",
    )


# /estimate dan /probe HARUS dideklarasikan sebelum "/{batch_id}", kalau tidak
# keduanya tertangkap sebagai batch_id.
@router.get(
    "/estimate",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
    },
    summary="Estimate how many reviews a cabang has, without calling Google",
)
def estimate_crawl(
    request: Request,
    onebox_location_id: int = Query(gt=0),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_crawl_queue_session_factory),
) -> dict:
    _require_scope(principal, "crawl:read")
    request_id = _request_id(request, x_request_id)
    try:
        data = _probe_service(session_factory).estimate(
            principal.company_id, onebox_location_id
        )
    except ReviewTargetNotFound as exc:
        raise _target_not_found(onebox_location_id) from exc
    return {
        "data": data,
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }


@router.get(
    "/probe",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        404: {"model": IntegrationErrorResponse},
    },
    summary="Ask Google whether a cabang's review count changed",
)
def probe_review_count(
    request: Request,
    onebox_location_id: int = Query(gt=0),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_crawl_queue_session_factory),
) -> dict:
    _require_scope(principal, "crawl:enqueue")
    request_id = _request_id(request, x_request_id)
    try:
        data = _probe_service(session_factory).probe(
            principal.company_id, onebox_location_id
        )
    except ReviewTargetNotFound as exc:
        raise _target_not_found(onebox_location_id) from exc
    return {
        "data": data,
        "meta": {"api_version": API_VERSION, "request_id": request_id},
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
        batch = CrawlQueue(session_factory=session_factory).get_batch(
            company_id=principal.company_id, public_id=batch_id
        )
    except CrawlQueueError as exc:
        raise _translate_queue_error(exc) from exc
    return {
        "data": batch,
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }
