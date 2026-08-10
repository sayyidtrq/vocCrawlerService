"""Ulasan kompetitor untuk OneBox.

Dipisah dari /integration/v1/reviews dengan sengaja. Endpoint itu mengalirkan
ulasan cabang yang menjadi tiket OneBox dan punya kursor sinkronisasi sendiri;
ulasan kompetitor tidak boleh ikut ke sana karena hanya bahan pembanding.
Karena itu jalurnya terpisah, hanya-baca, dan tanpa kursor.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select

from app.db.models import Competitor, CompetitorReview
from app.db.session import get_session_factory
from app.services.integration_review_service import IntegrationRequestError
from apps.api.app_api.integration_schemas import (
    API_VERSION,
    IntegrationErrorResponse,
)
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(
    prefix="/integration/v1/competitor-reviews", tags=["integration-competitor"]
)


def get_competitor_review_session_factory():
    return get_session_factory()


@router.get(
    "",
    responses={
        401: {"model": IntegrationErrorResponse},
        403: {"model": IntegrationErrorResponse},
    },
    summary="Ulasan kompetitor terbaru untuk tenant token ini",
)
def list_competitor_reviews(
    request: Request,
    limit: int = Query(default=8, ge=1, le=100),
    competitor_id: int | None = Query(default=None, gt=0),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    principal: ServicePrincipal = Depends(require_service_principal),
    session_factory=Depends(get_competitor_review_session_factory),
) -> dict:
    if "crawl:read" not in principal.scopes:
        raise IntegrationRequestError(
            403, "INSUFFICIENT_SCOPE", "Token lacks the crawl:read scope."
        )

    request_id = x_request_id or str(uuid4())
    request.state.request_id = request_id

    with session_factory() as session:
        # Join ke competitors bukan sekadar demi nama: itu yang mengikat baris
        # ke tenant. CompetitorReview tidak punya company_id sendiri, jadi tanpa
        # join ini satu token bisa membaca ulasan kompetitor milik tenant lain.
        dasar = (
            select(CompetitorReview, Competitor.name)
            .join(Competitor, Competitor.id == CompetitorReview.competitor_id)
            .where(Competitor.company_id == principal.company_id)
        )
        hitung = (
            select(func.count(CompetitorReview.id))
            .join(Competitor, Competitor.id == CompetitorReview.competitor_id)
            .where(Competitor.company_id == principal.company_id)
        )

        if competitor_id is not None:
            dasar = dasar.where(CompetitorReview.competitor_id == competitor_id)
            hitung = hitung.where(CompetitorReview.competitor_id == competitor_id)

        baris = session.execute(
            dasar.order_by(
                CompetitorReview.review_time.desc(),
                CompetitorReview.id.desc(),
            ).limit(limit)
        ).all()

        total = session.scalar(hitung) or 0

        data = [
            {
                "id": r.id,
                "competitor_id": r.competitor_id,
                "competitor_name": nama,
                "source": r.source,
                "rating": r.rating,
                "review_text": r.review_text,
                "reviewer_name": r.reviewer_name,
                "review_time": r.review_time,
                "review_relative_time": r.review_relative_time,
            }
            for r, nama in baris
        ]

    return {
        "data": data,
        "meta": {
            "api_version": API_VERSION,
            "request_id": request_id,
            "total": total,
        },
    }
