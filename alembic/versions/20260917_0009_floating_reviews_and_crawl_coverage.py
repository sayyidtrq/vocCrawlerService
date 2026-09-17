"""Floating-review fields, per-target crawl coverage, and the window log.

Revision ID: 20260917_0009
Revises: 20260915_0008
"""

import sqlalchemy as sa

from alembic import op

revision = "20260917_0009"
down_revision = "20260915_0008"
branch_labels = None
depends_on = None

_REVIEW_TABLES = ("reviews", "competitor_reviews")
_TARGET_TABLES = ("locations", "competitors")
_TZ = sa.DateTime(timezone=True)
_COVERAGE_COLUMNS = (
    ("newest_crawled_at", _TZ),
    ("newest_crawled_precision", sa.String(10)),
    ("oldest_crawled_at", _TZ),
    ("backfill_completed_at", _TZ),
    ("last_successful_crawl_at", _TZ),
    ("last_expected_review_count", sa.Integer()),
    ("last_probed_review_count", sa.Integer()),
    ("last_probed_at", _TZ),
    ("last_sweep_at", _TZ),
)


def upgrade() -> None:
    for table in _REVIEW_TABLES:
        op.add_column(table, sa.Column("review_time_precision", sa.String(10)))
        op.add_column(
            table,
            sa.Column(
                "is_edited",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )
        op.add_column(table, sa.Column("edited_at", _TZ))
    for table in _TARGET_TABLES:
        for name, column_type in _COVERAGE_COLUMNS:
            op.add_column(table, sa.Column(name, column_type))
    op.create_table(
        "crawl_window_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "competitor_id",
            sa.Integer(),
            sa.ForeignKey("competitors.id", ondelete="CASCADE"),
        ),
        sa.Column("crawl_job_id", sa.Integer()),
        sa.Column("date_from", _TZ),
        sa.Column("date_to", _TZ),
        sa.Column("completeness", sa.String(20), nullable=False),
        sa.Column("stop_reason", sa.String(50)),
        sa.Column(
            "finished_at", _TZ, server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "idx_crawl_window_log_location",
        "crawl_window_log",
        ["location_id", "finished_at"],
    )
    op.create_index(
        "idx_crawl_window_log_competitor",
        "crawl_window_log",
        ["competitor_id", "finished_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_crawl_window_log_competitor", table_name="crawl_window_log")
    op.drop_index("idx_crawl_window_log_location", table_name="crawl_window_log")
    op.drop_table("crawl_window_log")
    for table in reversed(_TARGET_TABLES):
        for name, _ in reversed(_COVERAGE_COLUMNS):
            op.drop_column(table, name)
    for table in reversed(_REVIEW_TABLES):
        op.drop_column(table, "edited_at")
        op.drop_column(table, "is_edited")
        op.drop_column(table, "review_time_precision")
