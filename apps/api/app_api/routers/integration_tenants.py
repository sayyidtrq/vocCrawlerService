"""Tenant provisioning for OneBox: register a site, read it, switch it, rotate its token."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, Request, Response, status

from app.services.integration_review_service import IntegrationRequestError
from app.services.tenant_registry_service import (
    TENANT_TOKEN_SCOPES,
    TenantNotFound,
    TenantRegistryService,
    TenantView,
)
from apps.api.app_api.integration_schemas import API_VERSION, IntegrationErrorResponse, to_utc_z
from apps.api.app_api.integration_tenant_schemas import (
    TenantCreateRequest,
    TenantRegisteredResponse,
    TenantResponse,
    TenantRotatedResponse,
    TenantUpdateRequest,
    TokenRotateRequest,
)
from apps.api.app_api.service_auth import require_provisioning_key

router = APIRouter(
    prefix="/integration/v1/tenants",
    tags=["integration-tenants"],
    dependencies=[Depends(require_provisioning_key)],
)
logger = logging.getLogger(__name__)

_ERRORS = {
    401: {"model": IntegrationErrorResponse},
    409: {"model": IntegrationErrorResponse},
    503: {"model": IntegrationErrorResponse},
}


def get_tenant_registry_service() -> TenantRegistryService:
    return TenantRegistryService()


def _request_id(request: Request, supplied: str | None) -> str:
    value = supplied or str(uuid4())
    request.state.request_id = value
    return value


def _meta(request_id: str) -> dict:
    return {"api_version": API_VERSION, "request_id": request_id}


def _iso(value) -> str | None:
    return to_utc_z(value) if value is not None else None


def _tenant_data(view: TenantView) -> dict:
    return {
        "company_id": view.company_id,
        "site_id": view.site_id,
        "site_name": view.site_name,
        "is_active": view.is_active,
        "deactivated_at": _iso(view.deactivated_at),
        "worklist": {
            "snapshot_version": view.worklist_snapshot_version,
            "applied_at": _iso(view.worklist_applied_at),
            "items": view.worklist_items,
            "last_error": view.worklist_last_error,
        },
        "credential": (
            {
                "key_id": view.token_key_id,
                "last_used_at": _iso(view.token_last_used_at),
                "expires_at": _iso(view.token_expires_at),
            }
            if view.token_key_id
            else None
        ),
    }


def _issued_token(issued) -> dict | None:
    if issued is None:
        return None
    return {
        "key_id": issued.client.key_id,
        "value": issued.token,
        "scopes": sorted(TENANT_TOKEN_SCOPES),
    }


def _not_found(exc: TenantNotFound) -> IntegrationRequestError:
    return IntegrationRequestError(404, "TENANT_NOT_FOUND", str(exc))


def _invalid(exc: ValueError) -> IntegrationRequestError:
    return IntegrationRequestError(400, "INVALID_PARAMETER", str(exc))


@router.post(
    "",
    response_model=TenantRegisteredResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Register a OneBox site as a tenant (idempotent)",
)
def register_tenant(
    payload: TenantCreateRequest,
    request: Request,
    response: Response,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    service: TenantRegistryService = Depends(get_tenant_registry_service),
) -> dict:
    request_id = _request_id(request, x_request_id)
    try:
        result = service.register(payload.site_id, payload.site_name)
    except ValueError as exc:
        raise _invalid(exc) from exc
    if not result.created:
        response.status_code = status.HTTP_200_OK
    logger.info(
        "tenant.registered",
        extra={"site_id": result.view.site_id, "company_id": result.view.company_id, "created": result.created},
    )
    return {
        "data": {
            **_tenant_data(result.view),
            "created": result.created,
            "token": _issued_token(result.token),
        },
        "meta": _meta(request_id),
    }


@router.get(
    "/{site_id}",
    response_model=TenantResponse,
    responses={**_ERRORS, 404: {"model": IntegrationErrorResponse}},
    summary="Read a tenant, including the worklist snapshot version it holds",
)
def get_tenant(
    site_id: int,
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    service: TenantRegistryService = Depends(get_tenant_registry_service),
) -> dict:
    request_id = _request_id(request, x_request_id)
    try:
        view = service.get(site_id)
    except TenantNotFound as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
    return {"data": _tenant_data(view), "meta": _meta(request_id)}


@router.patch(
    "/{site_id}",
    response_model=TenantResponse,
    responses={**_ERRORS, 404: {"model": IntegrationErrorResponse}},
    summary="Switch a tenant on or off, or rename it",
)
def update_tenant(
    site_id: int,
    payload: TenantUpdateRequest,
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    service: TenantRegistryService = Depends(get_tenant_registry_service),
) -> dict:
    request_id = _request_id(request, x_request_id)
    try:
        view = service.update(site_id, active=payload.active, site_name=payload.site_name)
    except TenantNotFound as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
    logger.info(
        "tenant.updated",
        extra={"site_id": view.site_id, "company_id": view.company_id, "is_active": view.is_active},
    )
    return {"data": _tenant_data(view), "meta": _meta(request_id)}


@router.post(
    "/{site_id}/token:rotate",
    response_model=TenantRotatedResponse,
    responses={**_ERRORS, 404: {"model": IntegrationErrorResponse}},
    summary="Issue a new tenant token; the old one stays valid for the overlap",
)
def rotate_tenant_token(
    site_id: int,
    request: Request,
    payload: TokenRotateRequest | None = Body(default=None),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    service: TenantRegistryService = Depends(get_tenant_registry_service),
) -> dict:
    request_id = _request_id(request, x_request_id)
    options = payload or TokenRotateRequest()
    try:
        issued = service.rotate_token(site_id, options.overlap_hours)
        view = service.get(site_id)
    except TenantNotFound as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
    logger.info(
        "tenant.token_rotated",
        extra={"site_id": view.site_id, "company_id": view.company_id, "key_id": issued.client.key_id},
    )
    return {
        "data": {**_tenant_data(view), "token": _issued_token(issued)},
        "meta": _meta(request_id),
    }
