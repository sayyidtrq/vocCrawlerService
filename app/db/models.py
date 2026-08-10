from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


JsonType = JSON().with_variant(JSONB, "postgresql")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_enable_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_enable_review: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analyze_competitor_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    locations: Mapped[list["Location"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    api_clients: Mapped[list["ApiClient"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    worklist_sync_states: Mapped[list["WorklistSyncState"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    crawl_batches: Mapped[list["CrawlBatch"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_company_id", "company_id"),
        Index("idx_users_email", "email", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="users")


class ApiClient(Base):
    """Opaque service credential bound to exactly one company tenant."""

    __tablename__ = "api_clients"
    __table_args__ = (
        Index("idx_api_clients_company_active", "company_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    key_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        JsonType,
        default=lambda: ["reviews:read"],
        server_default=text("""'["reviews:read"]'"""),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="api_clients")


class WorklistSyncState(Base):
    """Last pull outcome for the OneBox-owned worklist cache."""

    __tablename__ = "worklist_sync_states"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_worklist_sync_states_company"),
        Index("idx_worklist_sync_states_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    company: Mapped[Company] = relationship(back_populates="worklist_sync_states")


class CrawlBatch(Base):
    """Tenant-bound request that groups durable crawl jobs."""

    __tablename__ = "crawl_batches"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_crawl_batches_company_idempotency"
        ),
        Index("idx_crawl_batches_company_created", "company_id", "created_at"),
        Index("idx_crawl_batches_public_id", "public_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_client_id: Mapped[int] = mapped_column(
        ForeignKey("api_clients.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    slot: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(30), default="queued", server_default="queued", nullable=False
    )
    analyze_after_crawl: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="crawl_batches")
    jobs: Mapped[list["CrawlJob"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class CrawlJob(Base):
    """One location crawl claimed by a background worker with a recoverable lease."""

    __tablename__ = "crawl_jobs"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "location_id", name="uq_crawl_jobs_batch_location"
        ),
        # Pasangan kompetitor dari constraint di atas. Harus partial index,
        # bukan UniqueConstraint biasa: baris cabang punya competitor_id NULL
        # dan di PostgreSQL NULL dianggap saling berbeda, sehingga constraint
        # penuh tidak akan menjaga apa pun.
        Index(
            "uq_crawl_jobs_batch_competitor",
            "batch_id",
            "competitor_id",
            unique=True,
            postgresql_where=text("competitor_id IS NOT NULL"),
        ),
        Index("idx_crawl_jobs_competitor", "competitor_id"),
        Index("idx_crawl_jobs_claim", "status", "available_at", "lease_expires_at"),
        Index("idx_crawl_jobs_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_batches.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    # Satu baris job mewakili SALAH SATU dari cabang (location_id) atau
    # kompetitor (competitor_id), tidak pernah keduanya. Kompetitor tidak punya
    # cermin di tabel locations, jadi kedua kolom cabang harus boleh kosong.
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=True
    )
    onebox_location_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competitor_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="queued", server_default="queued", nullable=False
    )
    source_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    target_review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Rentang tanggal yang diminta pemanggil. Disimpan per job, bukan per batch,
    # karena tiap cabang boleh punya rentang sendiri.
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # newest | most_relevant | highest_rating | lowest_rating.
    # Kosong berarti newest — satu-satunya urutan yang menopang rentang tanggal.
    sort_by: Mapped[str | None] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3", nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[dict] = mapped_column(
        JsonType, default=dict, server_default=text("'{}'"), nullable=False
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[CrawlBatch] = relationship(back_populates="jobs")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint(
            "source", "external_place_id", name="uq_locations_source_place"
        ),
        Index("idx_locations_source_place", "source", "external_place_id"),
        Index("idx_locations_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    hospital_name: Mapped[str] = mapped_column(String(150), nullable=False)
    branch_name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    google_maps_url: Mapped[str | None] = mapped_column(Text)
    google_reviews_url: Mapped[str | None] = mapped_column(Text)
    target_review_count: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False
    )
    onebox_connection_id: Mapped[int | None] = mapped_column(Integer)
    onebox_location_id: Mapped[int | None] = mapped_column(Integer)
    crawl_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ingest_reviews: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worklist_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    fetch_logs: Mapped[list["FetchLog"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    company: Mapped[Company] = relationship(back_populates="locations")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_reviews_rating",
        ),
        Index("idx_reviews_location_id", "location_id"),
        Index("idx_reviews_review_time", "review_time"),
        Index("idx_reviews_rating", "rating"),
        Index("idx_reviews_review_hash", "review_hash"),
        Index("idx_reviews_source_place", "source", "external_place_id"),
        # Serves the integration keyset scan: tenant, then the exact ORDER BY.
        Index("idx_reviews_company_sync_id", "company_id", "sync_updated_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_place_id: Mapped[str | None] = mapped_column(String(255))
    external_review_id: Mapped[str | None] = mapped_column(String(255))
    reviewer_name: Mapped[str | None] = mapped_column(String(255))
    reviewer_profile_url: Mapped[str | None] = mapped_column(Text)
    reviewer_photo_url: Mapped[str | None] = mapped_column(Text)
    reviewer_local_guide_level: Mapped[str | None] = mapped_column(String(100))
    reviewer_total_reviews: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[int | None] = mapped_column(Integer)
    review_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_relative_time: Mapped[str | None] = mapped_column(String(100))
    review_language: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(20))
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_response_text: Mapped[str | None] = mapped_column(Text)
    owner_response_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    review_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Watermark OneBox pages on. Distinct from updated_at because analysis is
    # append-only: a review analysed weeks after it was scraped never touches
    # updated_at, but must still be resent. AnalysisService moves this in the
    # same transaction that writes the analysis. No onupdate= here on purpose —
    # every writer sets it explicitly, so a silent bump can't desync a consumer
    # mid-page.
    sync_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    location: Mapped[Location] = relationship(back_populates="reviews")
    analyses: Mapped[list["ReviewAnalysis"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class ReviewAnalysis(Base):
    __tablename__ = "review_analysis"
    __table_args__ = (
        Index("idx_review_analysis_review_id", "review_id"),
        Index("idx_review_analysis_sentiment", "sentiment"),
        Index("idx_review_analysis_issue_category", "issue_category"),
        Index("idx_review_analysis_urgency", "urgency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    sentiment: Mapped[str | None] = mapped_column(String(50))
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    issue_category: Mapped[str | None] = mapped_column(String(100))
    urgency: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list] = mapped_column(JsonType, default=list, nullable=False)
    is_potential_viral: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_patient_safety_issue: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    raw_response: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review: Mapped[Review] = relationship(back_populates="analyses")


class FetchLog(Base):
    __tablename__ = "fetch_logs"
    __table_args__ = (
        Index("idx_fetch_logs_location_id", "location_id"),
        Index("idx_fetch_logs_status", "status"),
        Index("idx_fetch_logs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(50))
    total_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JsonType, default=dict, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    location: Mapped[Location] = relationship(back_populates="fetch_logs")


class Competitor(Base):
    __tablename__ = "competitors"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_place_id",
            "company_id",
            name="uq_competitors_source_place_company",
        ),
        Index("idx_competitors_company_id", "company_id"),
        Index("idx_competitors_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    google_maps_url: Mapped[str | None] = mapped_column(Text)
    google_reviews_url: Mapped[str | None] = mapped_column(Text)
    target_review_count: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False
    )
    onebox_connection_id: Mapped[int | None] = mapped_column(Integer)
    onebox_location_id: Mapped[int | None] = mapped_column(Integer)
    crawl_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingest_reviews: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worklist_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="competitors")
    reviews: Mapped[list["CompetitorReview"]] = relationship(
        back_populates="competitor", cascade="all, delete-orphan"
    )


class CompetitorReview(Base):
    __tablename__ = "competitor_reviews"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_comp_reviews_rating",
        ),
        Index("idx_comp_reviews_competitor_id", "competitor_id"),
        Index("idx_comp_reviews_review_time", "review_time"),
        Index("idx_comp_reviews_review_hash", "review_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_place_id: Mapped[str | None] = mapped_column(String(255))
    external_review_id: Mapped[str | None] = mapped_column(String(255))
    reviewer_name: Mapped[str | None] = mapped_column(String(255))
    reviewer_profile_url: Mapped[str | None] = mapped_column(Text)
    reviewer_photo_url: Mapped[str | None] = mapped_column(Text)
    reviewer_local_guide_level: Mapped[str | None] = mapped_column(String(100))
    reviewer_total_reviews: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[int | None] = mapped_column(Integer)
    review_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_relative_time: Mapped[str | None] = mapped_column(String(100))
    review_language: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(20))
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_response_text: Mapped[str | None] = mapped_column(Text)
    owner_response_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    review_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    competitor: Mapped[Competitor] = relationship(back_populates="reviews")
