from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Company
from app.db.session import get_session_factory


class CompanyService:
    def __init__(
        self, session_factory: sessionmaker[Session] | None = None
    ) -> None:
        self.session_factory = session_factory or get_session_factory()

    def create(
        self,
        name: str,
        *,
        ai_enable_flag: bool = False,
        analyze_competitor_flag: bool = False,
        total_enable_review: int = 0,
    ) -> Company:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("name is required")
        if total_enable_review < 0:
            raise ValueError("total_enable_review must be zero or greater")

        company = Company(
            name=normalized_name,
            ai_enable_flag=ai_enable_flag,
            analyze_competitor_flag=analyze_competitor_flag,
            total_enable_review=total_enable_review,
        )
        with self.session_factory() as session:
            session.add(company)
            session.commit()
            session.refresh(company)
        return company

    def list_companies(self) -> list[Company]:
        with self.session_factory() as session:
            return list(session.scalars(select(Company).order_by(Company.id)))
