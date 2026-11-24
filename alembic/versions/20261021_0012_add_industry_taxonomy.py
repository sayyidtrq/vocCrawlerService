"""Add OneBox industry taxonomy snapshots, tags and risk flags.

Revision ID: 20261021_0012
Revises: 20261001_0011
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261021_0012"
down_revision: Union[str, None] = "20261001_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JsonType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("locations", sa.Column("taxonomy_key", sa.String(length=80), nullable=True))
    op.add_column("locations", sa.Column("taxonomy_version", sa.String(length=16), nullable=True))
    op.add_column("review_analysis", sa.Column("taxonomy_version", sa.String(length=16), nullable=True))
    op.add_column("review_analysis", sa.Column("risk_flags", JsonType, nullable=True))
    op.add_column("review_analysis", sa.Column("tags", JsonType, nullable=True))
    op.create_table(
        "taxonomy_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("body", JsonType, nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("company_id", "key", name="uq_taxonomy_snapshots_company_key"),
    )


def downgrade() -> None:
    op.drop_table("taxonomy_snapshots")
    op.drop_column("review_analysis", "tags")
    op.drop_column("review_analysis", "risk_flags")
    op.drop_column("review_analysis", "taxonomy_version")
    op.drop_column("locations", "taxonomy_version")
    op.drop_column("locations", "taxonomy_key")
