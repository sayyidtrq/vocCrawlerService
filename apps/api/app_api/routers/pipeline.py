from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.services.analysis_service import AnalysisService
from app.services.export_service import ExportService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.selenium_fetch_service import SeleniumFetchService
from apps.api.app_api.serializers import to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class LocationPipelineRequest(BaseModel):
    location_id: int
    fetch: bool = True
    analyze: bool = True
    export_csv: bool = False
    dry_run: bool = False
    target_review_count: int | None = Field(default=None, ge=1, le=300)
    source: str | None = None


@router.post(
    "/location",
    summary="Jalankan pipeline 1 lokasi (fetch → analyze → export)",
    description=(
        "Menjalankan beberapa langkah sekaligus untuk satu lokasi: crawling, analisis AI, "
        "dan export CSV — masing-masing bisa di-toggle (`fetch`, `analyze`, `export_csv`). "
        "Response berisi `steps` dengan hasil tiap langkah dan `status` keseluruhan."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "location_id": 5,
                        "source": "selenium",
                        "dry_run": False,
                        "status": "success",
                        "steps": {"fetch": {"status": "success"}, "analysis": {"total": 40}},
                    }
                }
            }
        },
        404: {"description": "Location not found"},
    },
)
def run_location_pipeline(payload: LocationPipelineRequest, principal: ServicePrincipal = Depends(require_service_principal)) -> dict:
    settings = get_settings()
    if LocationService(company_id=principal.company_id).get_location(payload.location_id) is None:
        raise ValueError("Location not found.")

    source = (payload.source or settings.review_source_mode).lower()
    result: dict = {
        "location_id": payload.location_id,
        "source": source,
        "dry_run": payload.dry_run,
        "steps": {},
        "status": "success",
    }

    if payload.fetch:
        if payload.dry_run:
            fetch_result = FetchService(company_id=principal.company_id).dry_run_location(payload.location_id)
        elif source in {"selenium", "selenium_google_maps"}:
            # Keep the Selenium path tenant-scoped just like the normal fetch
            # service. Without this company_id, a guessed location_id could
            # bypass the ownership check inside LocationService.
            fetch_result = SeleniumFetchService(
                company_id=principal.company_id
            ).fetch_location(
                payload.location_id,
                target=payload.target_review_count,
            )
        else:
            fetch_result = FetchService(company_id=principal.company_id).fetch_location(payload.location_id)
        result["steps"]["fetch"] = fetch_result
        if fetch_result.get("status") == "failed":
            result["status"] = "failed"
            return to_jsonable(result)

    if payload.analyze and not payload.dry_run:
        result["steps"]["analysis"] = AnalysisService(company_id=principal.company_id).analyze_pending(
            location_id=payload.location_id
        )

    if payload.export_csv and not payload.dry_run:
        export_path = ExportService(company_id=principal.company_id).export_location_reviews_csv(payload.location_id)
        result["steps"]["export"] = {
            "status": "success",
            "filename": export_path.name,
            "path": export_path,
        }

    return to_jsonable(result)
