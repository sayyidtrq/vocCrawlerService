from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Location
from app.db.session import get_session_factory
from app.services.location_repository import LocationRepository


def _optional_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a valid number.") from exc


class LocationService:
    editable_fields = {
        "hospital_name",
        "branch_name",
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

    def add_location(self, **data: object) -> Location:
        branch_name = str(data.get("branch_name") or "").strip()
        source = str(data.get("source") or "").strip()
        external_place_id = str(data.get("external_place_id") or "").strip()
        if not branch_name:
            raise ValueError("Branch name is required.")
        if not source:
            raise ValueError("Source is required.")
        if not external_place_id:
            raise ValueError("External place ID is required.")

        location = Location(
            hospital_name=str(data.get("hospital_name") or "Hermina").strip(),
            branch_name=branch_name,
            city=str(data.get("city") or "").strip() or None,
            address=str(data.get("address") or "").strip() or None,
            latitude=_optional_decimal(data.get("latitude"), "Latitude"),
            longitude=_optional_decimal(data.get("longitude"), "Longitude"),
            source=source,
            external_place_id=external_place_id,
            google_maps_url=str(data.get("google_maps_url") or "").strip() or None,
            google_reviews_url=(
                str(data.get("google_reviews_url") or "").strip() or None
            ),
            target_review_count=self._validate_target_count(
                data.get("target_review_count", 100)
            ),
            is_active=bool(data.get("is_active", True)),
            company_id=self.company_id,
        )
        with self.session_factory() as session:
            try:
                session.add(location)
                session.commit()
                session.refresh(location)
                return location
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(
                    "A location with this source and external place ID already exists."
                ) from exc

    def get_all_locations(
        self, active_only: bool = False, crawl_enabled_only: bool = False
    ) -> list[Location]:
        with self._read_session() as session:
            return LocationRepository(session, self.company_id).list(
                active_only=active_only,
                crawl_enabled_only=crawl_enabled_only,
            )

    def get_location(self, location_id: int) -> Location | None:
        with self._read_session() as session:
            return LocationRepository(session, self.company_id).get(location_id)

    def update_location(self, location_id: int, field: str, value: object) -> Location:
        if field not in self.editable_fields:
            raise ValueError("This location field cannot be updated.")
        with self.session_factory() as session:
            statement = select(Location).where(Location.id == location_id)
            if self.company_id is not None:
                statement = statement.where(Location.company_id == self.company_id)
            location = session.scalar(statement)
            if location is None:
                raise ValueError("Location not found.")

            if field in {"branch_name", "source", "external_place_id"}:
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
            elif field in {
                "city",
                "address",
                "google_maps_url",
                "google_reviews_url",
            }:
                value = str(value or "").strip() or None
            else:
                value = str(value or "").strip()

            setattr(location, field, value)
            try:
                session.commit()
                session.refresh(location)
                return location
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(
                    "A location with this source and external place ID already exists."
                ) from exc

    def toggle_active(self, location_id: int) -> Location:
        with self.session_factory() as session:
            statement = select(Location).where(Location.id == location_id)
            if self.company_id is not None:
                statement = statement.where(Location.company_id == self.company_id)
            location = session.scalar(statement)
            if location is None:
                raise ValueError("Location not found.")
            location.is_active = not location.is_active
            session.commit()
            session.refresh(location)
            return location

    def delete_location(self, location_id: int) -> str:
        with self.session_factory() as session:
            statement = select(Location).where(Location.id == location_id)
            if self.company_id is not None:
                statement = statement.where(Location.company_id == self.company_id)
            location = session.scalar(statement)
            if location is None:
                raise ValueError("Location not found.")
            branch_name = location.branch_name
            session.delete(location)
            session.commit()
            return branch_name

    @staticmethod
    def _validate_target_count(value: object) -> int:
        try:
            target = int(value or 100)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        if not 1 <= target <= 300:
            raise ValueError("Target review count must be between 1 and 300.")
        return target
