"""Merge the taxonomy and tenant registry migrations.

Both were written against 20261001_0011 in parallel, which left two heads and
made `alembic upgrade head` refuse to run. Nothing to change in the schema.

Revision ID: 20261022_0013
Revises: 20261021_0012, 20261022_0012
"""

from typing import Sequence, Union


revision: str = "20261022_0013"
down_revision: Union[str, Sequence[str], None] = ("20261021_0012", "20261022_0012")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
