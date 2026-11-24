"""OneBox integration contract v1.

Additive: nothing here touches GET /api/reviews, which the FE depends on.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select

from app.db.models import Company, Location
from app.db.session import get_session_factory
from app.services.integration_review_service import (
    IntegrationRequestError,
    IntegrationReviewService,
)
from app.utils.integration_cursor import CURSOR_VERSION, fingerprint
from apps.api.app_api.integration_schemas import (
    API_VERSION,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MIN_LIMIT,
    IntegrationErrorResponse,
    IntegrationReviewListResponse,
    ServiceIdentityResponse,
)
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration/v1", tags=["integration"])

REQUIRED_SCOPE = "reviews:read"


def get_integration_session_factory():
    """Seam for tests to point the contract at a disposable database."""
    return get_session_factory()


def _parse_updated_since(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    candidate = raw.strip()
    if candidate.endswith(("z", "Z")):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise IntegrationRequestError(
            400,
            "INVALID_PARAMETER",
            "updated_since must be a UTC ISO 8601 timestamp, e.g. 2026-07-01T00:00:00Z.",
        ) from exc
    if parsed.tzinfo is None:
        raise IntegrationRequestError(
            400,
            "INVALID_PARAMETER",
            "updated_since must carry an explicit UTC offset (Z).",
        )
    return parsed.astimezone(timezone.utc)


@router.get(
    "/whoami",
    response_model=ServiceIdentityResponse,
    summary="Validasi identity service token untuk OneBox",
    responses={401: {"model": IntegrationErrorResponse, "description": "Service token invalid"}},
)
def service_whoami(
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_integration_session_factory),
) -> dict:
    with session_factory() as session:
        company = session.scalar(select(Company).where(Company.id == principal.company_id))
    if company is None:
        raise IntegrationRequestError(401, "INVALID_SERVICE_TOKEN", "Invalid service token.")
    return {
        "company_id": company.id,
        "company_name": company.name,
        "scopes": sorted(principal.scopes),
    }

@router.get(
    "/locations/{onebox_location_id}",
    summary="Resolve OneBox location to Crawler location within the token tenant",
)
def resolve_integration_location(
    onebox_location_id: int,
    principal: Annotated[ServicePrincipal, Depends(require_service_principal)],
    session_factory: Annotated[object, Depends(get_integration_session_factory)],
) -> dict:
    if REQUIRED_SCOPE not in principal.scopes:
        raise IntegrationRequestError(403, "INSUFFICIENT_SCOPE", "Token lacks the reviews:read scope.")
    if onebox_location_id <= 0:
        raise IntegrationRequestError(400, "INVALID_PARAMETER", "onebox_location_id must be positive.")
    with session_factory() as session:
        locations = session.scalars(
            select(Location).where(
                Location.company_id == principal.company_id,
                Location.onebox_location_id == onebox_location_id,
            ).limit(2)
        ).all()
        if not locations:
            raise IntegrationRequestError(404, "LOCATION_NOT_FOUND", "Cabang belum ada di worklist Crawler; jalankan refresh_worklist.")
        if len(locations) != 1:
            raise IntegrationRequestError(409, "AMBIGUOUS_LOCATION", "Multiple Crawler locations map to this OneBox location.")
        return {"id": locations[0].id, "onebox_location_id": onebox_location_id}


@router.get(
    "/reviews",
    response_model=IntegrationReviewListResponse,
    summary="Pull review + analysis untuk OneBox (contract v1)",
    description=(
        "Endpoint pull khusus integrasi OneBox. Contract dibekukan di v1: field "
        "hanya bertambah (additive), tidak pernah dihapus atau berubah tipe. "
        "raw_payload/raw_response tidak pernah dikirim, dan company_id tidak "
        "muncul sebagai parameter maupun field response — tenant ditentukan oleh "
        "service token."
    ),
    responses={
        400: {"model": IntegrationErrorResponse, "description": "Parameter/cursor invalid"},
        401: {"model": IntegrationErrorResponse, "description": "Service token invalid"},
        403: {"model": IntegrationErrorResponse, "description": "Scope tidak cukup"},
        404: {"model": IntegrationErrorResponse, "description": "Location tidak ditemukan"},
    },
)
def list_integration_reviews(
    request: Request,
    limit: int = Query(default=DEFAULT_LIMIT, description="1..200"),
    cursor: str | None = Query(
        default=None,
        description=(
            "Opaque cursor dari next_cursor (lanjut siklus berjalan) atau "
            "checkpoint_cursor (mulai siklus berikutnya). Tidak boleh digabung "
            "dengan updated_since."
        ),
    ),
    updated_since: str | None = Query(
        default=None,
        description="UTC ISO 8601 (Z). Hanya untuk request pertama tanpa cursor.",
    ),
    location_id: int | None = Query(default=None),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_integration_session_factory),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict:
    started = time.perf_counter()
    request_id = x_request_id or str(uuid4())
    request.state.request_id = request_id

    if not (MIN_LIMIT <= limit <= MAX_LIMIT):
        raise IntegrationRequestError(
            400,
            "INVALID_PARAMETER",
            f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}.",
        )
    if REQUIRED_SCOPE not in principal.scopes:
        raise IntegrationRequestError(
            403, "INSUFFICIENT_SCOPE", "Token lacks the reviews:read scope."
        )

    parsed_updated_since = _parse_updated_since(updated_since)

    service = IntegrationReviewService(
        company_id=principal.company_id, session_factory=session_factory
    )
    result = service.list_reviews(
        limit=limit,
        cursor=cursor,
        updated_since=parsed_updated_since,
        location_id=location_id,
    )

    # Omits the token, review_text, and the cursor body — a logged cursor is a
    # replayable pointer into a tenant's data, so only a fingerprint goes out.
    logger.info(
        "integration.reviews.request",
        extra={
            "request_id": request_id,
            "key_id": principal.key_id,
            "company_id": principal.company_id,
            "cursor_version": CURSOR_VERSION,
            "cursor_fp": fingerprint(cursor) if cursor else None,
            "limit": limit,
            "location_id": location_id,
            "item_count": len(result["items"]),
            "has_more": result["has_more"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )

    return {
        "data": result["items"],
        "page": {
            "limit": limit,
            "has_more": result["has_more"],
            "next_cursor": result["next_cursor"],
            "checkpoint_cursor": result["checkpoint_cursor"],
            "snapshot_at": result["snapshot_at"],
        },
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }
