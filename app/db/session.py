from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # Supabase's session-mode pooler (port 5432) caps this project at 15 total
    # clients. SQLAlchemy's default pool (size 5 + overflow 10 = up to 15
    # held-open connections) can consume that entire budget on its own and
    # starve any other client (the terminal app, alembic, a second API worker),
    # which surfaces as intermittent 500s on login/other endpoints. Keep a
    # small bounded pool and recycle idle connections so we stay well under the
    # cap. For higher concurrency, point DATABASE_URL at the transaction pooler
    # (port 6543) instead of 5432.
    url = make_url(get_settings().database_url)
    if url.get_backend_name() == "sqlite":
        # SQLite memakai pool bawaannya sendiri (SingletonThreadPool untuk
        # :memory:) yang menolak max_overflow/pool_timeout. Hanya dev/test.
        return create_engine(url, pool_pre_ping=True)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1500,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


@contextmanager
def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

