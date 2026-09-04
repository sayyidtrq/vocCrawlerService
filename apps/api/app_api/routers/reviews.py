from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.services.review_service import ReviewService
from app.utils.date_parser import resolve_date_range
from apps.api.app_api.schemas import ReviewListResponse, ReviewResponse
from apps.api.app_api.serializers import hide_raw_payload, to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get(
    "",
    response_model=ReviewListResponse,
    summary="List review hasil crawling + insight AI",
    description=(
        "Ambil daftar review (paginated) beserta hasil analisis AI yang menempel "
        "pada tiap review. Mendukung filter lokasi, rating, sentiment, keyword, dan "
        "rentang tanggal. **Endpoint pull utama untuk integrasi Onebox.** "
        "Data otomatis di-scope ke company milik token."
    ),
)
def list_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    location_id: int | None = Query(default=None),
    rating: int | None = Query(default=None, ge=1, le=5),
    sentiment: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    latest_first: bool = Query(default=False),
    include_raw: bool = Query(default=False),
    date_preset: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    principal: ServicePrincipal = Depends(require_service_principal),
) -> dict:
    settings = get_settings()
    resolved_from, resolved_to = resolve_date_range(date_preset, date_from, date_to)
    service = ReviewService(company_id=principal.company_id)
    items, total = service.get_reviews(
        page=page,
        page_size=page_size,
        location_id=location_id,
        rating=rating,
        sentiment=sentiment,
        keyword=keyword,
        latest_first=latest_first,
        date_from=resolved_from,
        date_to=resolved_to,
    )
    if not (settings.show_raw_payload or include_raw):
        items = [hide_raw_payload(item) for item in items]
    return to_jsonable(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )


@router.get(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Detail satu review",
    description="Ambil satu review beserta hasil analisis AI-nya. Set `include_raw=true` untuk menyertakan payload mentah.",
    responses={404: {"description": "Review not found"}},
)
def get_review(
    review_id: int,
    include_raw: bool = Query(default=False),
    principal: ServicePrincipal = Depends(require_service_principal),
) -> dict:
    settings = get_settings()
    service = ReviewService(company_id=principal.company_id)
    review = service.get_review(review_id)
    if review is None:
        raise ValueError("Review not found.")
    if not (settings.show_raw_payload or include_raw):
        review = hide_raw_payload(review)
    return to_jsonable(review)
