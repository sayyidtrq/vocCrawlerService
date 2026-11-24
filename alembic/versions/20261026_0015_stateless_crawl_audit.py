"""Add independent v2 crawl audit tables."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20261026_0015"
down_revision = "20261026_0014"
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "audit_crawl_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("site_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("place_id", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("params", JsonType, nullable=False),
        sa.Column("handle", JsonType, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="started"),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_polled_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", "idempotency_key", "place_id", name="uq_audit_crawl_runs_site_key_place"),
    )
    op.create_index("idx_audit_crawl_runs_site_place", "audit_crawl_runs", ["site_id", "place_id"])
    op.create_table(
        "audit_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("place_id", sa.String(255), nullable=False),
        sa.Column("review_hash", sa.String(255), nullable=False),
        sa.Column("payload", JsonType, nullable=False),
        sa.Column("review_time", sa.DateTime(timezone=True)),
        sa.Column("first_run_id", sa.String(64)),
        sa.Column("last_run_id", sa.String(64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("site_id", "review_hash", name="uq_audit_reviews_site_hash"),
    )
    op.create_index("idx_audit_reviews_site_place", "audit_reviews", ["site_id", "place_id"])
    op.create_index("idx_audit_reviews_review_time", "audit_reviews", ["review_time"])


def downgrade() -> None:
    op.drop_index("idx_audit_reviews_review_time", table_name="audit_reviews")
    op.drop_index("idx_audit_reviews_site_place", table_name="audit_reviews")
    op.drop_table("audit_reviews")
    op.drop_index("idx_audit_crawl_runs_site_place", table_name="audit_crawl_runs")
    op.drop_table("audit_crawl_runs")
