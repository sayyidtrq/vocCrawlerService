"""Persist Apify cursors so credit exhaustion never restarts a target.

Revision ID: 20260915_0008
Revises: 20260826_0007
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260915_0008"
down_revision = "20260826_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column(
            "apify_resume_checkpoint",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "competitors",
        sa.Column(
            "apify_resume_checkpoint",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("competitors", "apify_resume_checkpoint")
    op.drop_column("locations", "apify_resume_checkpoint")
