from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.models import User
from app.integrations.local_llm_client import LocalLLMClient
from app.services.analysis_service import AnalysisService
from app.services.entitlement_service import EntitlementError, EntitlementService
from apps.api.app_api.dependencies import get_current_user
from apps.api.app_api.schemas import AnalysisPendingResponse
from apps.api.app_api.serializers import to_jsonable

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalyzePendingRequest(BaseModel):
    location_id: int | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class RollbackAnalysesRequest(BaseModel):
    model_name: str = Field(min_length=1, description="Model yang hasilnya dibuang.")
    since: datetime | None = Field(
        default=None,
        description="Hanya baris dari model_name yang dibuat setelah waktu ini. Kosong = seluruh riwayat model_name.",
    )


def _require_ai_enabled(company_id: int) -> None:
    try:
        EntitlementService(company_id).require_ai_enabled()
    except EntitlementError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/models",
    summary="Daftar model AI yang tersedia pada deployment Crawler ini",
)
def available_models(current_user: User = Depends(get_current_user)) -> dict:
    _require_ai_enabled(current_user.company_id)
    settings = get_settings()
    try:
        models = LocalLLMClient(settings).list_models()
    except Exception as exc:  # noqa: BLE001 - provider SDKs expose varied errors
        raise HTTPException(
            status_code=502,
            detail="AI provider tidak dapat mengembalikan daftar model.",
        ) from exc
    return {"models": models, "default_model": settings.local_llm_model}


@router.post(
    "/pending",
    response_model=AnalysisPendingResponse,
    summary="Jalankan analisis AI untuk review pending",
    description="Analisis semua review yang belum dianalisis (opsional difilter `location_id`/`rating`). Butuh `ai_enable_flag` aktif (else 403).",
    responses={403: {"description": "AI belum diaktifkan untuk company ini"}},
)
def analyze_pending(payload: AnalyzePendingRequest, current_user: User = Depends(get_current_user)) -> dict:
    _require_ai_enabled(current_user.company_id)
    result = AnalysisService(company_id=current_user.company_id).analyze_pending(
        location_id=payload.location_id, rating=payload.rating,
    )
    return to_jsonable(result)


@router.post(
    "/locations/{location_id}/rerun",
    summary="Ulang analisis AI 1 lokasi",
    description="Jalankan ulang analisis AI untuk semua review pada satu lokasi. Butuh `ai_enable_flag` aktif.",
    responses={
        200: {"content": {"application/json": {"example": {"total": 40, "success": 38, "failed": 2}}}},
        403: {"description": "AI belum diaktifkan untuk company ini"},
    },
)
def rerun_location(location_id: int, current_user: User = Depends(get_current_user)) -> dict:
    _require_ai_enabled(current_user.company_id)
    return to_jsonable(AnalysisService(company_id=current_user.company_id).rerun_location(location_id))


@router.post(
    "/reviews/{review_id}/rerun",
    summary="Ulang analisis AI 1 review",
    description="Jalankan ulang analisis AI untuk satu review. Butuh `ai_enable_flag` aktif.",
    responses={
        200: {"content": {"application/json": {"example": {"sentiment": "negative", "sentiment_score": -0.82, "issue_category": "waktu_tunggu", "urgency": "high", "summary": "..."}}}},
        403: {"description": "AI belum diaktifkan untuk company ini"},
    },
)
def rerun_review(review_id: int, current_user: User = Depends(get_current_user)) -> dict:
    _require_ai_enabled(current_user.company_id)
    result = AnalysisService(company_id=current_user.company_id).rerun_review(review_id)
    if int(result.get("failed") or 0) > 0:
        raise HTTPException(
            status_code=502,
            detail="AI provider gagal menganalisis review setelah retry.",
        )
    return to_jsonable(result)


@router.post(
    "/rollback",
    summary="Prosedur rollback: buang hasil satu model AI",
    description=(
        "Buang seluruh ReviewAnalysis milik model_name (opsional dibatasi `since`). "
        "Review yang terdampak kembali ke jawaban model sebelumnya bila ada, atau ke "
        "pending untuk dianalisa ulang. Dipakai ketika sebuah model/prompt terbukti "
        "menghasilkan analisa yang salah secara sistematis — bukan untuk satu review "
        "yang gagal, itu cukup lewat /reviews/{id}/rerun."
    ),
)
def rollback_analyses(
    payload: RollbackAnalysesRequest, current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AnalysisService(company_id=current_user.company_id).rollback_analyses(
            model_name=payload.model_name, since=payload.since,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_jsonable(result)


@router.get(
    "/quality-summary",
    summary="Sebaran status analisa dalam N jam terakhir",
    description="Sinyal kesehatan murah untuk monitoring/alerting — porsi failed yang melonjak menandakan AI bermasalah.",
)
def quality_summary(
    hours: int = 24, current_user: User = Depends(get_current_user),
) -> dict:
    return AnalysisService(company_id=current_user.company_id).quality_summary(hours=hours)
