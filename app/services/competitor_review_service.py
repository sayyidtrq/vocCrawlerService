from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import CompetitorReview
from app.db.session import get_session_factory
from app.services.review_repository import insert_review_optimistically


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
            statement = self._dedupe_statement(review)
            return insert_review_optimistically(
                session, review, lambda: session.scalar(statement)
            )

    @staticmethod
    def _dedupe_statement(review: CompetitorReview):
        predicates = [CompetitorReview.review_hash == review.review_hash]
        external_review_id = (review.external_review_id or "").strip()
        if external_review_id:
            predicates.append(
                and_(
                    CompetitorReview.competitor_id == review.competitor_id,
                    CompetitorReview.source == review.source,
                    CompetitorReview.external_review_id == external_review_id,
                )
            )
        return select(CompetitorReview.id).where(or_(*predicates))
