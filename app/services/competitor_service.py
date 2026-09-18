from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import DEFAULT_REVIEW_LIMIT, MAX_REVIEW_LIMIT
from app.db.models import Competitor
from app.db.session import get_session_factory

def _optional_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a valid number.") from exc

class CompetitorService:
    editable_fields = {
        "name",
        "city",
        "address",
        "latitude",
        "longitude",
        "source",
        "external_place_id",
        "google_maps_url",
        "google_reviews_url",
        "target_review_count",
        "is_active",
    }

    def __init__(self, company_id: int, session_factory: sessionmaker[Session] | None = None):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()

    def add_competitor(self, **data: object) -> Competitor:
        name = str(data.get("name") or "").strip()
        source = str(data.get("source") or "").strip()
        external_place_id = str(data.get("external_place_id") or "").strip()
        if not name:
            raise ValueError("Competitor name is required.")
        if not source:
            raise ValueError("Source is required.")
        if not external_place_id:
            raise ValueError("External place ID is required.")

        competitor = Competitor(
            company_id=self.company_id,
            name=name,
            city=str(data.get("city") or "").strip() or None,
            address=str(data.get("address") or "").strip() or None,
            latitude=_optional_decimal(data.get("latitude"), "Latitude"),
            longitude=_optional_decimal(data.get("longitude"), "Longitude"),
            source=source,
            external_place_id=external_place_id,
            google_maps_url=str(data.get("google_maps_url") or "").strip() or None,
            google_reviews_url=str(data.get("google_reviews_url") or "").strip() or None,
            target_review_count=self._validate_target_count(data.get("target_review_count", DEFAULT_REVIEW_LIMIT)),
            is_active=bool(data.get("is_active", True)),
        )
        with self.session_factory() as session:
            try:
                session.add(competitor)
                session.commit()
                session.refresh(competitor)
                return competitor
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("A competitor with this source and external place ID already exists for your company.") from exc

    def get_all_competitors(self, active_only: bool = False) -> list[Competitor]:
        with self.session_factory() as session:
            statement = select(Competitor).where(Competitor.company_id == self.company_id).order_by(Competitor.id)
            if active_only:
                statement = statement.where(Competitor.is_active.is_(True))
            return list(session.scalars(statement))

    def get_competitor(self, competitor_id: int) -> Competitor | None:
        with self.session_factory() as session:
            return session.scalar(
                select(Competitor).where(Competitor.id == competitor_id, Competitor.company_id == self.company_id)
            )

    def update_competitor(self, competitor_id: int, field: str, value: object) -> Competitor:
        if field not in self.editable_fields:
            raise ValueError("This competitor field cannot be updated.")
        with self.session_factory() as session:
            competitor = session.scalar(
                select(Competitor).where(Competitor.id == competitor_id, Competitor.company_id == self.company_id)
            )
            if competitor is None:
                raise ValueError("Competitor not found.")

            if field in {"name", "source", "external_place_id"}:
                clean_value = str(value or "").strip()
                if not clean_value:
                    raise ValueError(f"{field} is required.")
                value = clean_value
            elif field in {"latitude", "longitude"}:
                value = _optional_decimal(value, field.title())
            elif field == "is_active":
                if isinstance(value, str):
                    value = value.strip().lower() in {"1", "true", "yes", "y"}
                else:
                    value = bool(value)
            elif field == "target_review_count":
                value = self._validate_target_count(value)
            elif field in {"city", "address", "google_maps_url", "google_reviews_url"}:
                value = str(value or "").strip() or None
            else:
                value = str(value or "").strip()

            setattr(competitor, field, value)
            try:
                session.commit()
                session.refresh(competitor)
                return competitor
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("A competitor with this source and external place ID already exists.") from exc

    def toggle_active(self, competitor_id: int) -> Competitor:
        with self.session_factory() as session:
            competitor = session.scalar(
                select(Competitor).where(Competitor.id == competitor_id, Competitor.company_id == self.company_id)
            )
            if competitor is None:
                raise ValueError("Competitor not found.")
            competitor.is_active = not competitor.is_active
            session.commit()
            session.refresh(competitor)
            return competitor

    def delete_competitor(self, competitor_id: int) -> str:
        with self.session_factory() as session:
            competitor = session.scalar(
                select(Competitor).where(Competitor.id == competitor_id, Competitor.company_id == self.company_id)
            )
            if competitor is None:
                raise ValueError("Competitor not found.")
            name = competitor.name
            session.delete(competitor)
            session.commit()
            return name

    @staticmethod
    def _validate_target_count(value: object) -> int:
        try:
            target = int(value or DEFAULT_REVIEW_LIMIT)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        if not 1 <= target <= MAX_REVIEW_LIMIT:
            raise ValueError(
                f"Target review count must be between 1 and {MAX_REVIEW_LIMIT}."
            )
        return target
