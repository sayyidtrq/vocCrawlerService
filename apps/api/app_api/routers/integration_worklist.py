"""OneBox pushes a tenant's full worklist snapshot."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.session import get_session_factory
from app.services.integration_review_service import IntegrationRequestError
from app.services.worklist_sync_service import (
    WorklistNotManagedError,
    WorklistSnapshotInvalidError,
    WorklistSyncError,
    WorklistSyncService,
    WorklistTenantInactiveError,
    WorklistTenantNotLinkedError,
)
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal

router = APIRouter(prefix="/integration/v1/worklist", tags=["integration-worklist"])
logger = logging.getLogger(__name__)

REQUIRED_SCOPE = "worklist:write"
# Tenant terbesar yang direncanakan ~100 cabang; batas ini menjaga worker API dari
# kiriman rusak, bukan membatasi pemakaian wajar.
MAX_SNAPSHOT_ITEMS = 5_000


def get_worklist_session_factory():
    return get_session_factory()


class WorklistPushRequest(BaseModel):
    """Tenant tidak pernah dibaca dari body; ia diturunkan dari token."""

    snapshot_version: Annotated[int, Field(strict=True, gt=0)]
    # Informasi untuk operator; tidak dipakai untuk menentukan versi.
    generated_at: str | None = None
    # list[Any]: isi tiap item divalidasi service supaya pesan errornya spesifik.
    items: list[Any] = Field(max_length=MAX_SNAPSHOT_ITEMS)


class WorklistPushData(BaseModel):
    status: str
    snapshot_version: int | None
    company_id: int
    site_id: int
    fetched: int
    upserted: int
    deactivated: int
    applied_at: str | None


class WorklistPushMeta(BaseModel):
    api_version: str
    request_id: str


class WorklistPushResponse(BaseModel):
    data: WorklistPushData
    meta: WorklistPushMeta


def _error(exc: WorklistSyncError) -> IntegrationRequestError:
    if isinstance(exc, WorklistSnapshotInvalidError):
        return IntegrationRequestError(400, "INVALID_SNAPSHOT", str(exc))
    if isinstance(exc, WorklistTenantInactiveError):
        return IntegrationRequestError(409, "TENANT_INACTIVE", str(exc))
    if isinstance(exc, WorklistNotManagedError):
        return IntegrationRequestError(409, "TENANT_MODE_NOT_MANAGED", str(exc))
    if isinstance(exc, WorklistTenantNotLinkedError):
        return IntegrationRequestError(409, "TENANT_NOT_LINKED", str(exc))
    logger.error("worklist.push_failed", extra={"error": str(exc)})
    return IntegrationRequestError(500, "WORKLIST_PUSH_FAILED", "The worklist could not be applied.")


@router.put(
    "",
    response_model=WorklistPushResponse,
    responses={
        400: {"model": IntegrationErrorResponse},
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
        409: {"model": IntegrationErrorResponse},
    },
    summary="Replace the tenant's worklist with a full, versioned snapshot",
)
def push_worklist(
    payload: WorklistPushRequest,
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_worklist_session_factory),
) -> dict:
    if REQUIRED_SCOPE not in principal.scopes:
        raise IntegrationRequestError(
            403, "INSUFFICIENT_SCOPE", f"Token lacks the {REQUIRED_SCOPE} scope."
        )
    request_id = x_request_id or str(uuid4())
    request.state.request_id = request_id
    try:
        result = WorklistSyncService(
            company_id=principal.company_id,
            session_factory=session_factory,
            settings=get_settings(),
        ).apply_snapshot(payload.snapshot_version, payload.items)
    except WorklistSyncError as exc:
        raise _error(exc) from exc
    logger.info(
        "worklist.pushed",
        extra={
            "company_id": result.company_id,
            "site_id": result.site_id,
            "status": result.status,
            "snapshot_version": result.snapshot_version,
        },
    )
    return {
        "data": {
            "status": result.status,
            "snapshot_version": result.snapshot_version,
            "company_id": result.company_id,
            "site_id": result.site_id,
            "fetched": result.fetched,
            "upserted": result.upserted,
            "deactivated": result.deactivated,
            "applied_at": result.last_success_at,
        },
        "meta": {"api_version": API_VERSION, "request_id": request_id},
    }
