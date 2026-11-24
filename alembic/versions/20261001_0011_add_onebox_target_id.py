"""Add OneBox target registry ids to cached targets.

Revision ID: 20261001_0011
Revises: 20260929_0010
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0011"
down_revision: Union[str, None] = "20260929_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("onebox_target_id", sa.Integer(), nullable=True))
    op.create_index("idx_locations_onebox_target", "locations", ["onebox_target_id"])
    op.add_column("competitors", sa.Column("onebox_target_id", sa.Integer(), nullable=True))
    op.create_index("idx_competitors_onebox_target", "competitors", ["onebox_target_id"])


def downgrade() -> None:
    op.drop_index("idx_competitors_onebox_target", table_name="competitors")
    op.drop_column("competitors", "onebox_target_id")
    op.drop_index("idx_locations_onebox_target", table_name="locations")
    op.drop_column("locations", "onebox_target_id")
