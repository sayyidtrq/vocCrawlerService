from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Review, ReviewAnalysis
from app.db.session import get_session_factory
from app.services.review_repository import (
    ReviewRepository,
    apply_resighting,
    backfill_missing_fields,
    insert_review_optimistically,
)


class ReviewService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        *,
        session: Session | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self._session = session

    @contextmanager
    def _read_session(self):
        if self._session is not None:
            yield self._session
        else:
            with self.session_factory() as session:
                yield session

    def review_hash_exists(self, review_hash: str) -> bool:
        with self.session_factory() as session:
            return (
                ReviewRepository(session, self.company_id).find_id_by_hash(review_hash)
                is not None
            )

    def insert_review(self, data: dict) -> tuple[Review | None, bool]:
        if self.company_id is not None and "company_id" not in data:
            data["company_id"] = self.company_id
        review = Review(**data)
        with self.session_factory() as session:
            repo = ReviewRepository(session, self.company_id)

            def enrich(existing_id: int, incoming: Review) -> None:
                # Review yang ditarik sebelum include_personal menyala punya
                # identitas pengulas kosong. Menariknya lagi hanya menemukan
                # duplikat lalu melewatinya, jadi perbaikannya ditempelkan di
                # sini: satu crawl ulang sekarang mengisi nama yang hilang.
                existing = session.get(Review, existing_id)
                filled = backfill_missing_fields(session, existing, incoming)
                resighted, content_changed = apply_resighting(existing, incoming)
                if content_changed:
                    # Isi ulasan berubah (diedit pengulas): analisa lama basi.
                    existing.analysis_status = "pending"
                if filled or resighted:
                    # Tanpa ini perbaikannya berhenti di DB Crawler: OneBox
                    # hanya menarik ulang review yang sync_updated_at-nya maju,
                    # dan kolom itu sengaja tanpa onupdate= (lihat models.py).
                    # Ekspresinya sama dengan AnalysisService demi urutan keyset.
                    existing.sync_updated_at = (
                        func.clock_timestamp()
                        if session.bind.dialect.name == "postgresql"
                        else datetime.now(timezone.utc)
                    )
                    session.commit()

            return insert_review_optimistically(
                session,
                review,
                lambda: repo.find_existing_dedupe_id(review),
                enrich=enrich,
            )

    def insert_reviews_bulk(
        self, items: list[dict], batch_size: int = 200
    ) -> list[tuple[Review | None, bool]]:
        """Simpan sekumpulan ulasan sekaligus dalam transaksi chunk."""
        if not items:
            return []
        results: list[tuple[Review | None, bool]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]
            results.extend(self._insert_chunk(chunk))
        return results

    def _insert_chunk(
        self, chunk: list[dict]
    ) -> list[tuple[Review | None, bool]]:
        from sqlalchemy import or_, select

        chunk_results: list[tuple[Review | None, bool]] = []
        with self.session_factory() as session:
            candidates: list[Review] = []
            hashes: set[str] = set()
            ext_ids: set[str] = set()
            for d in chunk:
                payload = dict(d)
                if self.company_id is not None and "company_id" not in payload:
                    payload["company_id"] = self.company_id
                rev = Review(**payload)
                candidates.append(rev)
                if rev.review_hash:
                    hashes.add(rev.review_hash)
                if rev.external_review_id:
                    ext_ids.add(rev.external_review_id.strip())

            predicates = []
            if hashes:
                predicates.append(Review.review_hash.in_(hashes))
            if ext_ids:
                predicates.append(Review.external_review_id.in_(ext_ids))

            existing_map_by_hash: dict[str, Review] = {}
            existing_map_by_ext: dict[tuple[str, str | None, str], Review] = {}

            if predicates:
                stmt = select(Review).where(or_(*predicates))
                if self.company_id is not None:
                    stmt = stmt.where(Review.company_id == self.company_id)
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
                    resighted, content_changed = apply_resighting(existing, rev)
                    if content_changed:
                        existing.analysis_status = "pending"
                    if filled or resighted:
                        existing.sync_updated_at = (
                            func.clock_timestamp()
                            if session.bind.dialect.name == "postgresql"
                            else datetime.now(timezone.utc)
                        )
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

    def review_exists(self, data: dict) -> bool:
        """Apakah review ini sudah tersimpan (aturan dedup yang sama)."""
        payload = dict(data)
        if self.company_id is not None:
            payload.setdefault("company_id", self.company_id)
        review = Review(**payload)
        with self.session_factory() as session:
            repo = ReviewRepository(session, self.company_id)
            return repo.find_existing_dedupe_id(review) is not None

    def get_review(self, review_id: int) -> dict | None:
        with self._read_session() as session:
            row = ReviewRepository(
                session, self.company_id
            ).get_with_latest_analysis(review_id)
            return self._row_to_dict(row) if row else None

    def get_reviews(
        self,
        page: int = 1,
        page_size: int = 20,
        location_id: int | None = None,
        rating: int | None = None,
        sentiment: str | None = None,
        keyword: str | None = None,
        latest_first: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[dict], int]:
        with self._read_session() as session:
            rows, total = ReviewRepository(
                session, self.company_id
            ).list_with_latest_analysis(
                page=page,
                page_size=page_size,
                location_id=location_id,
                rating=rating,
                sentiment=sentiment,
                keyword=keyword,
                latest_first=latest_first,
                date_from=date_from,
                date_to=date_to,
            )
            return [self._row_to_dict(row) for row in rows], total

    def get_all_export_rows(self, location_id: int | None = None) -> list[dict]:
        page_size = 500
        page = 1
        output: list[dict] = []
        while True:
            rows, total = self.get_reviews(
                page=page, page_size=page_size, location_id=location_id
            )
            output.extend(rows)
            if len(output) >= total:
                return output
            page += 1

    @staticmethod
    def _row_to_dict(row) -> dict:
        review: Review = row[0]
        branch_name: str = row[1]
        analysis: ReviewAnalysis | None = row[2]
        return {
            "id": review.id,
            "location_id": review.location_id,
            "location": branch_name,
            "source": review.source,
            "external_place_id": review.external_place_id,
            "external_review_id": review.external_review_id,
            "reviewer_name": review.reviewer_name or "Anonymous",
            "reviewer_profile_url": review.reviewer_profile_url,
            "reviewer_photo_url": review.reviewer_photo_url,
            "reviewer_local_guide_level": review.reviewer_local_guide_level,
            "reviewer_total_reviews": review.reviewer_total_reviews,
            "rating": review.rating,
            "review_text": review.review_text,
            "review_time": review.review_time,
            "review_relative_time": review.review_relative_time,
            "review_language": review.review_language,
            "language": review.language,
            "like_count": review.like_count,
            "owner_response_text": review.owner_response_text,
            "owner_response_time": review.owner_response_time,
            "scraped_at": review.scraped_at,
            "raw_payload": review.raw_payload,
            "review_hash": review.review_hash,
            "created_at": review.created_at,
            "analysis_status": review.analysis_status,
            "analyzed": analysis is not None,
            "analysis_id": analysis.id if analysis else None,
            "sentiment": analysis.sentiment if analysis else None,
            "sentiment_score": (
                float(analysis.sentiment_score)
                if analysis and analysis.sentiment_score is not None
                else None
            ),
            "issue_category": analysis.issue_category if analysis else None,
            "urgency": analysis.urgency if analysis else None,
            "summary": analysis.summary if analysis else None,
            "recommended_action": analysis.recommended_action if analysis else None,
            "keywords": analysis.keywords if analysis else [],
            "is_potential_viral": (
                analysis.is_potential_viral if analysis else False
            ),
            "is_patient_safety_issue": (
                analysis.is_patient_safety_issue if analysis else False
            ),
        }
