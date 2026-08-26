"""Persist the latest AI analysis attempt status on reviews.

Revision ID: 20260812_0006
Revises: 20260805_0005
"""

import sqlalchemy as sa
from alembic import op


revision = "20260812_0006"
down_revision = "20260805_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column(
            "analysis_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_reviews_analysis_status",
        "reviews",
        "analysis_status IN ('pending', 'completed', 'failed', 'incomplete')",
    )
    op.execute(
        """
        UPDATE reviews
           SET analysis_status = CASE
               WHEN NOT EXISTS (
                   SELECT 1 FROM review_analysis ra WHERE ra.review_id = reviews.id
               ) THEN 'pending'
               WHEN EXISTS (
                   SELECT 1
                     FROM review_analysis ra
                    WHERE ra.id = (
                        SELECT MAX(latest.id)
                          FROM review_analysis latest
                         WHERE latest.review_id = reviews.id
                    )
                      AND NULLIF(TRIM(COALESCE(ra.urgency, '')), '') IS NOT NULL
                      AND NULLIF(TRIM(COALESCE(ra.issue_category, '')), '') IS NOT NULL
                      AND NULLIF(TRIM(COALESCE(ra.summary, '')), '') IS NOT NULL
                      AND NULLIF(TRIM(COALESCE(ra.recommended_action, '')), '') IS NOT NULL
               ) THEN 'completed'
               ELSE 'incomplete'
           END
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_reviews_analysis_status", "reviews", type_="check")
    op.drop_column("reviews", "analysis_status")
