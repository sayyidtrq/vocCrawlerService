"""Projection and delta-sync pull for the OneBox v1 integration contract.

Separate from ``ReviewService`` on purpose. ReviewService serves the FE and is
free to change shape; this one is pinned to the published contract. The
projection lists every exported field explicitly rather than dumping the model
and popping a blacklist, so a new column on ``Review`` (or a new secret on
``ReviewAnalysis``) can never leak to the consumer by default.

Paging is keyset over ``(sync_updated_at, id)`` inside a frozen snapshot, not
offset. Offset is wrong here: rows enter and move within the ordering while
OneBox is mid-cycle, so an OFFSET page would silently skip and duplicate reviews.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Location, Review, ReviewAnalysis
from app.db.session import get_session_factory
from app.utils.integration_cursor import (
    CURSOR_VERSION,
    CursorPosition,
    IntegrationCursor,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)

# Lower bound for a consumer that has never synced. Exclusive, and every real id
# is >= 1, so nothing is missed.
EPOCH = CursorPosition(sync_updated_at=datetime(1970, 1, 1, tzinfo=timezone.utc), id=0)


class IntegrationRequestError(Exception):
    """Maps 1:1 onto the contract's error envelope."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _latest_analysis_subquery():
    # Intentionally not imported from review_service: that helper exists to serve
    # the FE, and the contract must not shift if it is retuned for FE reasons.
    return (
        select(
            ReviewAnalysis.review_id.label("review_id"),
            func.max(ReviewAnalysis.id).label("analysis_id"),
        )
        .group_by(ReviewAnalysis.review_id)
        .subquery()
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # SQLite drops tzinfo on round-trip; everything is written as UTC.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class IntegrationReviewService:
    def __init__(
        self,
        company_id: int,
        session_factory: sessionmaker[Session] | None = None,
        cursor_secret: str | None = None,
    ) -> None:
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self.cursor_secret = (
            cursor_secret or get_settings().integration_cursor_secret
        )

    # ----------------------------------------------------------------- public

    def list_reviews(
        self,
        limit: int,
        cursor: str | None = None,
        updated_since: datetime | None = None,
        location_id: int | None = None,
    ) -> dict:
        decoded = self._resolve_cursor(cursor, updated_since, location_id)
        # A follow-up page may send the cursor alone; the filter it was opened
        # with lives inside it, so it survives without the consumer resending it.
        if decoded is not None:
            location_id = decoded.location_id

        with self.session_factory() as session:
            self._assert_location_in_tenant(session, location_id)

            lower, upper = self._resolve_bounds(
                session, decoded, updated_since, location_id
            )
            rows = self._fetch_page(session, lower, upper, location_id, limit)

        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [self._project(row) for row in rows]

        next_cursor = None
        checkpoint_cursor = None
        if has_more:
            last = rows[-1][0]
            next_cursor = self._encode(
                location_id,
                lower=CursorPosition(_as_utc(last.sync_updated_at), last.id),
                upper=upper,
            )
        else:
            # Snapshot drained. The checkpoint's lower == upper, which is how the
            # next cycle recognises it should open a fresh upper bound from here
            # instead of replaying this exhausted snapshot.
            checkpoint_cursor = self._encode(location_id, lower=upper, upper=upper)

        return {
            "items": items,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "checkpoint_cursor": checkpoint_cursor,
            "snapshot_at": datetime.now(timezone.utc),
        }

    # ---------------------------------------------------------------- cursors

    def _resolve_cursor(
        self,
        cursor: str | None,
        updated_since: datetime | None,
        location_id: int | None,
    ) -> IntegrationCursor | None:
        if cursor is None:
            return None
        if updated_since is not None:
            # updated_since is a bootstrap lower bound. Honouring it alongside a
            # cursor would silently move the page window and drop rows.
            raise IntegrationRequestError(
                400,
                "INVALID_CURSOR_CONTEXT",
                "cursor cannot be combined with updated_since.",
            )
        try:
            decoded = decode_cursor(cursor, self.cursor_secret, self.company_id)
        except InvalidCursorError as exc:
            raise IntegrationRequestError(
                400, "INVALID_CURSOR", "Cursor is invalid."
            ) from exc

        # Omitting location_id is fine — the cursor already carries it. Naming a
        # different one is not: narrowing or widening the filter mid-cycle moves
        # rows across the cursor position, and they would never be paged.
        if location_id is not None and location_id != decoded.location_id:
            raise IntegrationRequestError(
                400,
                "INVALID_CURSOR_CONTEXT",
                "location_id does not match the cursor it was issued with.",
            )
        return decoded

    def _encode(
        self, location_id: int | None, lower: CursorPosition, upper: CursorPosition
    ) -> str:
        return encode_cursor(
            IntegrationCursor(
                version=CURSOR_VERSION,
                company_id=self.company_id,
                location_id=location_id,
                lower=lower,
                upper=upper,
                issued_at=datetime.now(timezone.utc),
            ),
            self.cursor_secret,
        )

    # ------------------------------------------------------------------ query

    def _assert_location_in_tenant(
        self, session: Session, location_id: int | None
    ) -> None:
        if location_id is None:
            return
        owned = session.scalar(
            select(Location.id).where(
                Location.id == location_id,
                Location.company_id == self.company_id,
            )
        )
        # Same 404 whether the location is absent or owned by another tenant:
        # distinguishing them would confirm its existence.
        if owned is None:
            raise IntegrationRequestError(
                404, "LOCATION_NOT_FOUND", "Location not found."
            )

    def _current_upper(
        self, session: Session, location_id: int | None
    ) -> CursorPosition | None:
        statement = (
            select(Review.sync_updated_at, Review.id)
            .where(Review.company_id == self.company_id)
            .order_by(Review.sync_updated_at.desc(), Review.id.desc())
            .limit(1)
        )
        if location_id is not None:
            statement = statement.where(Review.location_id == location_id)
        row = session.execute(statement).first()
        if row is None:
            return None
        return CursorPosition(sync_updated_at=_as_utc(row[0]), id=row[1])

    def _resolve_bounds(
        self,
        session: Session,
        decoded: IntegrationCursor | None,
        updated_since: datetime | None,
        location_id: int | None,
    ) -> tuple[CursorPosition, CursorPosition]:
        if decoded is None:
            lower = (
                CursorPosition(sync_updated_at=updated_since, id=0)
                if updated_since is not None
                else EPOCH
            )
            upper = self._current_upper(session, location_id)
        elif decoded.is_checkpoint:
            # Next cycle: everything up to the old checkpoint is already ingested,
            # so re-open the ceiling at whatever exists now.
            lower = decoded.lower
            upper = self._current_upper(session, location_id)
        else:
            # Mid-cycle: the ceiling stays frozen at the value the snapshot opened
            # with, so rows written while OneBox pages cannot shift the window.
            lower = decoded.lower
            upper = decoded.upper

        if upper is None:
            # Nothing in this tenant/filter at all. Collapsing upper onto lower
            # yields an empty page and a checkpoint the consumer can resume from.
            upper = lower
        return lower, upper

    def _fetch_page(
        self,
        session: Session,
        lower: CursorPosition,
        upper: CursorPosition,
        location_id: int | None,
        limit: int,
    ) -> list:
        latest = _latest_analysis_subquery()
        statement = (
            select(Review, Location.branch_name, ReviewAnalysis)
            .join(Location, Location.id == Review.location_id)
            .outerjoin(latest, latest.c.review_id == Review.id)
            .outerjoin(ReviewAnalysis, ReviewAnalysis.id == latest.c.analysis_id)
            .where(Review.company_id == self.company_id)
            # Lower-exclusive, upper-inclusive, tie-broken by id. Rows sharing a
            # timestamp are common (a batch commits together), so without the id
            # tie-break a page boundary landing inside such a group would drop or
            # repeat rows.
            .where(
                or_(
                    Review.sync_updated_at > lower.sync_updated_at,
                    and_(
                        Review.sync_updated_at == lower.sync_updated_at,
                        Review.id > lower.id,
                    ),
                )
            )
            .where(
                or_(
                    Review.sync_updated_at < upper.sync_updated_at,
                    and_(
                        Review.sync_updated_at == upper.sync_updated_at,
                        Review.id <= upper.id,
                    ),
                )
            )
            .order_by(Review.sync_updated_at.asc(), Review.id.asc())
        )
        if location_id is not None:
            statement = statement.where(Review.location_id == location_id)

        # limit + 1: the extra row is only a has_more probe and is never returned.
        return session.execute(statement.limit(limit + 1)).all()

    # ------------------------------------------------------------- projection

    @staticmethod
    def _project(row) -> dict:
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
            "review_hash": review.review_hash,
            "reviewer_name": review.reviewer_name,
            "reviewer_profile_url": review.reviewer_profile_url,
            "rating": review.rating,
            "review_text": review.review_text,
            "review_time": _as_utc(review.review_time),
            "owner_response_text": review.owner_response_text,
            "owner_response_time": _as_utc(review.owner_response_time),
            "updated_at": _as_utc(review.updated_at),
            "sync_updated_at": _as_utc(review.sync_updated_at),
            "analysis_status": review.analysis_status,
            "analyzed": analysis is not None,
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
            "keywords": list(analysis.keywords) if analysis else [],
            "is_potential_viral": (
                bool(analysis.is_potential_viral) if analysis else False
            ),
            "is_patient_safety_issue": (
                bool(analysis.is_patient_safety_issue) if analysis else False
            ),
        }
