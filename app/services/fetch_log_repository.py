from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from app.db.models import FetchLog, Location


class FetchLogRepository:
    def __init__(self, session: Session, company_id: int | None = None):
        self.session = session
        self.company_id = company_id

    def recent(
        self,
        *,
        location_id: int | None,
        failed_only: bool,
        limit: int,
    ) -> list[Row]:
        statement = (
            select(FetchLog, Location.branch_name)
            .join(Location, Location.id == FetchLog.location_id)
            .order_by(FetchLog.started_at.desc(), FetchLog.id.desc())
            .limit(limit)
        )
        if self.company_id is not None:
            statement = statement.where(FetchLog.company_id == self.company_id)
        if location_id is not None:
            statement = statement.where(FetchLog.location_id == location_id)
        if failed_only:
            statement = statement.where(FetchLog.status == "failed")
        return self.session.execute(statement).all()
