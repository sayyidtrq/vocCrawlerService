from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import get_session_factory


def get_db_session() -> Session:
    factory = get_session_factory()
    with factory() as session:
        yield session
