"""Add append-only v2 AI audit history."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20261027_0016"
down_revision = "20261026_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_ref", sa.String(64), nullable=False),
        sa.Column("review_hash", sa.String(255)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("taxonomy_key", sa.String(80)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_analyses_site_hash", "audit_analyses", ["site_id", "review_hash"])
    op.create_index("idx_audit_analyses_site_created", "audit_analyses", ["site_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_analyses_site_created", table_name="audit_analyses")
    op.drop_index("idx_audit_analyses_site_hash", table_name="audit_analyses")
    op.drop_table("audit_analyses")
