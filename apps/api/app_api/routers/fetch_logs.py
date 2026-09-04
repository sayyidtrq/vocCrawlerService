from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.services.fetch_log_service import FetchLogService
from apps.api.app_api.schemas import FetchLogLatestResponse, FetchLogListResponse
from apps.api.app_api.serializers import to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(prefix="/fetch-logs", tags=["fetch logs"])


@router.get(
    "",
    response_model=FetchLogListResponse,
    summary="List log crawling",
    description=(
        "Ambil riwayat log crawling (fetch jobs). Filter opsional `location_id`, "
        "`failed_only=true` untuk hanya yang gagal, dan `limit` (1–200)."
    ),
)
def list_fetch_logs(
    location_id: int | None = Query(default=None),
    failed_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=200),
    principal: ServicePrincipal = Depends(require_service_principal),
) -> dict:
    logs = FetchLogService(company_id=principal.company_id).get_logs(
        location_id=location_id,
        failed_only=failed_only,
        limit=limit,
    )
    return to_jsonable({"items": logs, "total": len(logs)})


@router.get(
    "/latest",
    response_model=FetchLogLatestResponse,
    summary="Log crawling terakhir",
    description="Ambil satu log crawling paling baru untuk company. `item` bernilai null jika belum ada log.",
)
def latest_fetch_log(principal: ServicePrincipal = Depends(require_service_principal)) -> dict:
    log = FetchLogService(company_id=principal.company_id).get_last_log()
    return to_jsonable({"item": log})
