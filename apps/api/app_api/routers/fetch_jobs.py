from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.services.entitlement_service import EntitlementService
from app.services.fetch_service import FetchService
from app.services.selenium_fetch_service import SeleniumFetchService
from app.utils.date_parser import resolve_date_range
from apps.api.app_api.serializers import to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(prefix="/fetch-jobs", tags=["fetch jobs"])


class FetchJobRequest(BaseModel):
    location_id: int
    source: str | None = None
    target_review_count: int | None = Field(default=None, ge=1, le=300)
    dry_run: bool = False
    date_preset: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class FetchAllActiveRequest(BaseModel):
    dry_run: bool = False
    date_preset: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def _resolve_range(payload) -> tuple[datetime | None, datetime | None]:
    return resolve_date_range(payload.date_preset, payload.date_from, payload.date_to)


_FETCH_RESULT_EXAMPLE = {
    "location_id": 5,
    "location_name": "Hermina Depok",
    "source": "selenium_google_maps",
    "status": "success",
    "total_fetched": 200,
    "total_inserted": 25,
    "total_duplicate": 175,
    "total_failed": 0,
    "total_skipped_out_of_range": 0,
    "error_message": None,
    "metadata": {"target_review_count": 200},
}


@router.post(
    "",
    summary="Trigger crawling 1 lokasi",
    description=(
        "Menjalankan crawling review untuk satu lokasi (sinkron/blocking). "
        "Mendukung `source` (selenium/places/mock), `dry_run`, dan rentang tanggal. "
        "`status` bisa `success` | `partial_success` | `failed` | `dry_run`."
    ),
    responses={200: {"content": {"application/json": {"example": _FETCH_RESULT_EXAMPLE}}}},
)
def run_fetch_job(payload: FetchJobRequest, principal: ServicePrincipal = Depends(require_service_principal)) -> dict:
    source = (payload.source or get_settings().review_source_mode).lower()
    date_from, date_to = _resolve_range(payload)

    if payload.target_review_count is not None:
        quota = EntitlementService(principal.company_id).review_quota()
        if quota > 0 and payload.target_review_count > quota:
            raise HTTPException(
                status_code=400,
                detail=f"Target review count exceeds your plan quota ({quota}).",
            )

    if payload.dry_run:
        result = FetchService(company_id=principal.company_id).dry_run_location(
            payload.location_id, date_from=date_from, date_to=date_to
        )
    elif source in {"selenium", "selenium_google_maps"}:
        try:
            result = SeleniumFetchService(company_id=principal.company_id).fetch_location(
                payload.location_id,
                target=payload.target_review_count,
                date_from=date_from,
                date_to=date_to,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        result = FetchService(company_id=principal.company_id).fetch_location(
            payload.location_id, date_from=date_from, date_to=date_to
        )
    return to_jsonable(result)


@router.post(
    "/all-active",
    summary="Trigger crawling semua lokasi aktif",
    description="Menjalankan crawling untuk seluruh lokasi aktif milik company. Mengembalikan ringkasan agregat beserta hasil per lokasi.",
    responses={200: {"content": {"application/json": {"example": {"status": "success", "total_locations": 12, "total_fetched": 2400, "results": [_FETCH_RESULT_EXAMPLE]}}}}},
)
def run_fetch_all_active(payload: FetchAllActiveRequest | None = None, principal: ServicePrincipal = Depends(require_service_principal)) -> dict:
    payload = payload or FetchAllActiveRequest()
    dry_run = bool(payload.dry_run)
    date_from, date_to = _resolve_range(payload)
    service = FetchService(company_id=principal.company_id)
    if not dry_run:
        return to_jsonable(service.fetch_all_active_locations(date_from=date_from, date_to=date_to))

    locations = service.location_service.get_all_locations(active_only=True)
    results = [
        service.dry_run_location(location.id, date_from=date_from, date_to=date_to)
        for location in locations
    ]
    return to_jsonable(
        {
            "status": "dry_run",
            "total_locations": len(locations),
            "total_fetched": sum(result.get("total_fetched", 0) for result in results),
            "results": results,
        }
    )
