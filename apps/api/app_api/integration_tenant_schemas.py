"""Tenant provisioning contract consumed by OneBox (isolated like integration_schemas)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.services.tenant_registry_service import (
    DEFAULT_ROTATION_OVERLAP_HOURS,
    MAX_ROTATION_OVERLAP_HOURS,
)

SiteId = Annotated[int, Field(strict=True, gt=0)]
SiteName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class TenantCreateRequest(BaseModel):
    """Field lain (mis. weight, settings) diabaikan dulu; kolomnya menyusul."""

    site_id: SiteId
    site_name: SiteName


class TenantUpdateRequest(BaseModel):
    active: bool | None = None
    site_name: SiteName | None = None


class TokenRotateRequest(BaseModel):
    overlap_hours: int = Field(
        default=DEFAULT_ROTATION_OVERLAP_HOURS, ge=0, le=MAX_ROTATION_OVERLAP_HOURS
    )


class WorklistState(BaseModel):
    snapshot_version: int | None = None
    applied_at: str | None = None
    items: int = 0
    last_error: str | None = None


class CredentialInfo(BaseModel):
    key_id: str
    last_used_at: str | None = None
    expires_at: str | None = None


class IssuedToken(BaseModel):
    """Satu-satunya tempat token mentah muncul; tidak bisa dibaca lagi sesudahnya."""

    key_id: str
    value: str
    scopes: list[str]


class Usage(BaseModel):
    operating_period: str
    backfill_fetched_total: int
    operating_fetched_month: int


class TenantData(BaseModel):
    company_id: int
    site_id: int
    site_name: str
    is_active: bool
    deactivated_at: str | None = None
    worklist: WorklistState
    credential: CredentialInfo | None = None
    usage: Usage


class TenantRegisteredData(TenantData):
    created: bool
    token: IssuedToken | None = None


class TenantRotatedData(TenantData):
    token: IssuedToken


class Meta(BaseModel):
    api_version: str
    request_id: str


class TenantResponse(BaseModel):
    data: TenantData
    meta: Meta


class TenantRegisteredResponse(BaseModel):
    data: TenantRegisteredData
    meta: Meta


class TenantRotatedResponse(BaseModel):
    data: TenantRotatedData
    meta: Meta
