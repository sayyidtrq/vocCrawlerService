from __future__ import annotations

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import CompetitorReview
from app.db.session import get_session_factory


class CompetitorReviewService:
    """Penyimpanan ulasan kompetitor.

    Dipisah dari ReviewService dengan sengaja. Tabel `reviews` adalah yang
    mengalir ke pipeline tiket OneBox; ulasan kompetitor tidak boleh ikut ke
    sana karena hanya berperan sebagai bahan pembanding. Karena itu ulasan
    kompetitor mendarat di `competitor_reviews` dan tidak pernah bercampur.
    """

    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()

    @staticmethod
    def _columns() -> set[str]:
        return {
            attr.key for attr in sa_inspect(CompetitorReview).mapper.column_attrs
        }

    def insert_review(
        self, competitor_id: int, data: dict
    ) -> tuple[CompetitorReview | None, bool]:
        """Simpan satu ulasan kompetitor; True kedua berarti duplikat.

        Payload datang dari normalizer yang sama dengan cabang, jadi isinya
        memuat kolom milik `reviews` yang tidak ada di sini (`location_id`,
        `company_id`). Disaring lewat daftar kolom model supaya penambahan
        kolom di salah satu tabel tidak diam-diam merusak yang lain.
        """
        allowed = self._columns()
        payload = {key: value for key, value in data.items() if key in allowed}
        payload["competitor_id"] = competitor_id
        if payload.get("review_text") is None:
            payload["review_text"] = ""
        review = CompetitorReview(**payload)
        with self.session_factory() as session:
            statement = select(CompetitorReview.id).where(
                CompetitorReview.review_hash == review.review_hash
            )
            existing = session.scalar(statement)
            if existing is not None:
                return None, True
            try:
                session.add(review)
                session.commit()
                session.refresh(review)
                return review, False
            except IntegrityError:
                # review_hash unik secara global: balapan antar worker mendarat
                # di sini, dan itu duplikat, bukan kegagalan.
                session.rollback()
                existing = session.scalar(statement)
                if existing is not None:
                    return None, True
                raise
