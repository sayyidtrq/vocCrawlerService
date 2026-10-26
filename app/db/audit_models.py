from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import JsonType


class AuditCrawlRun(Base):
    __tablename__ = "audit_crawl_runs"
    __table_args__ = (
        Index("idx_audit_crawl_runs_site_place", "site_id", "place_id"),
        UniqueConstraint(
            "site_id", "idempotency_key", "place_id",
            name="uq_audit_crawl_runs_site_key_place",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    params: Mapped[dict] = mapped_column(JsonType, nullable=False)
    handle: Mapped[dict] = mapped_column(JsonType, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="started", server_default="started", nullable=False)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditReview(Base):
    __tablename__ = "audit_reviews"
    __table_args__ = (
        UniqueConstraint("site_id", "review_hash", name="uq_audit_reviews_site_hash"),
        Index("idx_audit_reviews_site_place", "site_id", "place_id"),
        Index("idx_audit_reviews_review_time", "review_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    review_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    review_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_run_id: Mapped[str | None] = mapped_column(String(64))
    last_run_id: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seen_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
