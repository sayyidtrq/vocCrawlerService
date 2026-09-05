from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.services.summary_service import SummaryService
from apps.api.app_api.dependencies import get_db_session
from apps.api.app_api.schemas import (
    DashboardOverviewResponse,
    IssueListResponse,
    LocationSummaryResponse,
)
from apps.api.app_api.serializers import to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="Ringkasan agregat seluruh company",
    description="Statistik gabungan: total lokasi & review, jumlah teranalisis/pending, distribusi sentiment, top issue, dan waktu fetch terakhir.",
)
def overview(
    principal: ServicePrincipal = Depends(require_service_principal),
    session: Session = Depends(get_db_session),
) -> dict:
    return to_jsonable(
        SummaryService(
            company_id=principal.company_id, session=session
        ).overall_summary()
    )


@router.get(
    "/locations/{location_id}",
    response_model=LocationSummaryResponse,
    summary="Ringkasan per lokasi",
    description="Statistik agregat untuk satu lokasi: rata-rata rating, sentiment, top issue, contoh review negatif, dan fokus manajemen.",
)
def location_summary(
    location_id: int,
    principal: ServicePrincipal = Depends(require_service_principal),
    session: Session = Depends(get_db_session),
) -> dict:
    return to_jsonable(
        SummaryService(
            company_id=principal.company_id, session=session
        ).location_summary(location_id)
    )


@router.get(
    "/critical-issues",
    response_model=IssueListResponse,
    summary="Daftar isu kritis",
    description="Daftar review yang teridentifikasi sebagai isu kritis (mis. patient safety / urgency tinggi) beserta rekomendasi aksi.",
)
def critical_issues(
    principal: ServicePrincipal = Depends(require_service_principal),
    session: Session = Depends(get_db_session),
) -> dict:
    items = SummaryService(
        company_id=principal.company_id, session=session
    ).critical_issues()
    return to_jsonable({"items": items, "total": len(items)})


@router.get(
    "/negative-reviews",
    response_model=IssueListResponse,
    summary="Daftar review negatif",
    description="Daftar review dengan sentiment negatif beserta kategori isu dan urgency.",
)
def negative_reviews(
    principal: ServicePrincipal = Depends(require_service_principal),
    session: Session = Depends(get_db_session),
) -> dict:
    items = SummaryService(
        company_id=principal.company_id, session=session
    ).negative_reviews()
    return to_jsonable({"items": items, "total": len(items)})
