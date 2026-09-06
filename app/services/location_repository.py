from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Location


class LocationRepository:
    def __init__(self, session: Session, company_id: int | None = None):
        self.session = session
        self.company_id = company_id

    def get(self, location_id: int) -> Location | None:
        statement = select(Location).where(Location.id == location_id)
        if self.company_id is not None:
            statement = statement.where(Location.company_id == self.company_id)
        return self.session.scalar(statement)

    def list(
        self,
        *,
        active_only: bool = False,
        crawl_enabled_only: bool = False,
    ) -> list[Location]:
        statement = select(Location).order_by(Location.id)
        if self.company_id is not None:
            statement = statement.where(Location.company_id == self.company_id)
        if active_only:
            statement = statement.where(Location.is_active.is_(True))
        if crawl_enabled_only:
            statement = statement.where(Location.crawl_enabled.is_(True))
        return list(self.session.scalars(statement))
