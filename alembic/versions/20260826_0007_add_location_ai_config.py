"""Cache the OneBox-owned AI analysis config on locations.

OneBox is the control plane for AI analysis (DNGO19-3388): it picks the model,
flips the per-connection switch, and names the output schema it expects back.
Those three arrive on every worklist row; before this revision the crawler
parsed the row and threw them away, so OneBox's choice never reached the code
that actually calls the model.

Revision ID: 20260826_0007
Revises: 20260812_0006
"""

import sqlalchemy as sa
from alembic import op


revision = "20260826_0007"
down_revision = "20260812_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column(
            "ai_enabled",
            sa.Boolean(),
            # Existing rows default to enabled, matching OneBox's own default.
            # Backfilling false would stop analysis for every branch running
            # today the moment this migration lands - a regression with no
            # configuration change behind it to explain it, and one that shows
            # up only as reviews quietly arriving without summaries.
            server_default=sa.true(),
            nullable=False,
        ),
    )
    # Nullable with no default: null means "OneBox has not chosen", which the
    # analyzer reads as "fall back to LOCAL_LLM_MODEL". Backfilling a concrete
    # model name here would be a lie about who chose it, and it would go stale
    # the first time the default model changes.
    op.add_column(
        "locations", sa.Column("ai_model", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "locations",
        sa.Column("ai_output_schema_version", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("locations", "ai_output_schema_version")
    op.drop_column("locations", "ai_model")
    op.drop_column("locations", "ai_enabled")
