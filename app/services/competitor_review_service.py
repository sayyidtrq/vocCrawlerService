from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import CompetitorReview
from app.db.session import get_session_factory
from app.services.review_repository import (
    apply_resighting,
    backfill_missing_fields,
    insert_review_optimistically,
)


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

            def enrich(existing_id: int, incoming: CompetitorReview) -> None:
                # Sama seperti review cabang: identitas pengulas kosong pada
                # semua yang ditarik sebelum include_personal menyala.
                existing = session.get(CompetitorReview, existing_id)
                filled = backfill_missing_fields(session, existing, incoming)
                resighted, _ = apply_resighting(existing, incoming)
                if filled or resighted:
                    session.commit()

            return insert_review_optimistically(
                session,
                review,
                lambda: session.scalar(statement),
                enrich=enrich,
            )

    def insert_reviews_bulk(
        self, competitor_id: int, items: list[dict], batch_size: int = 200
    ) -> list[tuple[CompetitorReview | None, bool]]:
        """Simpan sekumpulan ulasan kompetitor dalam transaksi chunk."""
        if not items:
            return []
        results: list[tuple[CompetitorReview | None, bool]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]
            results.extend(self._insert_chunk(competitor_id, chunk))
        return results

    def _insert_chunk(
        self, competitor_id: int, chunk: list[dict]
    ) -> list[tuple[CompetitorReview | None, bool]]:
        from sqlalchemy import or_, select

        chunk_results: list[tuple[CompetitorReview | None, bool]] = []
        allowed = self._columns()
        with self.session_factory() as session:
            candidates: list[CompetitorReview] = []
            hashes: set[str] = set()
            ext_ids: set[str] = set()
            for d in chunk:
                payload = {key: value for key, value in d.items() if key in allowed}
                payload["competitor_id"] = competitor_id
                if payload.get("review_text") is None:
                    payload["review_text"] = ""
                rev = CompetitorReview(**payload)
                candidates.append(rev)
                if rev.review_hash:
                    hashes.add(rev.review_hash)
                if rev.external_review_id:
                    ext_ids.add(rev.external_review_id.strip())

            predicates = []
            if hashes:
                predicates.append(CompetitorReview.review_hash.in_(hashes))
            if ext_ids:
                predicates.append(CompetitorReview.external_review_id.in_(ext_ids))

            existing_map_by_hash: dict[str, CompetitorReview] = {}
            existing_map_by_ext: dict[tuple[str, str | None, str], CompetitorReview] = {}

            if predicates:
                stmt = select(CompetitorReview).where(
                    CompetitorReview.competitor_id == competitor_id,
                    or_(*predicates),
                )
                existing_rows = session.scalars(stmt).all()
                for r in existing_rows:
                    if r.review_hash:
                        existing_map_by_hash[r.review_hash] = r
                    if r.external_review_id:
                        key = (r.source, r.external_place_id, r.external_review_id.strip())
                        existing_map_by_ext[key] = r

            for rev in candidates:
                existing = None
                if rev.review_hash and rev.review_hash in existing_map_by_hash:
                    existing = existing_map_by_hash[rev.review_hash]
                elif rev.external_review_id:
                    key = (rev.source, rev.external_place_id, rev.external_review_id.strip())
                    existing = existing_map_by_ext.get(key)

                if existing is not None:
                    filled = backfill_missing_fields(session, existing, rev)
                    resighted, _ = apply_resighting(existing, rev)
                    chunk_results.append((existing, True))
                else:
                    session.add(rev)
                    if rev.review_hash:
                        existing_map_by_hash[rev.review_hash] = rev
                    if rev.external_review_id:
                        key = (rev.source, rev.external_place_id, rev.external_review_id.strip())
                        existing_map_by_ext[key] = rev
                    chunk_results.append((rev, False))

            session.commit()
        return chunk_results

    def review_exists(self, competitor_id: int, data: dict) -> bool:
        allowed = self._columns()
        payload = {key: value for key, value in data.items() if key in allowed}
        payload["competitor_id"] = competitor_id
        review = CompetitorReview(**payload)
        with self.session_factory() as session:
            return session.scalar(self._dedupe_statement(review)) is not None

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
