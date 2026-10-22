"""Mirror OneBox sites as tenants and track the applied worklist snapshot.

Revision ID: 20261022_0012
Revises: 20261001_0011
"""

import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261022_0012"
down_revision: Union[str, None] = "20261001_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def backfill_onebox_site_id(bind) -> None:
    """Tautkan company ke site hanya bila tidak ambigu.

    worklist_sync_states unik per company, jadi sebuah site yang muncul di lebih
    dari satu baris dipakai lebih dari satu company (mis. sisa refresh lintas
    tenant). Menebak pemiliknya akan menanam salah-tautan di kolom unik, jadi
    yang ambigu dibiarkan kosong dan dicatat untuk diputuskan manual. Tidak
    menimpa tautan yang sudah ada, sehingga aman dijalankan ulang.
    """
    bind.execute(
        sa.text(
            """
            UPDATE companies
            SET onebox_site_id = (
                SELECT s.site_id FROM worklist_sync_states s WHERE s.company_id = companies.id
            )
            WHERE onebox_site_id IS NULL
              AND EXISTS (
                SELECT 1 FROM worklist_sync_states s
                WHERE s.company_id = companies.id
                  AND (SELECT COUNT(*) FROM worklist_sync_states d WHERE d.site_id = s.site_id) = 1
                  AND NOT EXISTS (SELECT 1 FROM companies c2 WHERE c2.onebox_site_id = s.site_id)
              )
            """
        )
    )
    ambiguous = bind.execute(
        sa.text(
            "SELECT site_id, COUNT(*) FROM worklist_sync_states "
            "GROUP BY site_id HAVING COUNT(*) > 1"
        )
    ).all()
    for site_id, companies in ambiguous:
        logger.warning(
            "companies.onebox_site_id left empty: OneBox site %s appears for %s companies; link it manually",
            site_id,
            companies,
        )


def upgrade() -> None:
    op.add_column("companies", sa.Column("onebox_site_id", sa.Integer(), nullable=True))
    op.add_column(
        "companies",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("companies", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("worklist_sync_states", sa.Column("snapshot_version", sa.BigInteger(), nullable=True))
    op.add_column("worklist_sync_states", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))

    backfill_onebox_site_id(op.get_bind())

    # Dibuat setelah backfill supaya data ambigu tidak menggagalkan migration.
    op.create_index("uq_companies_onebox_site", "companies", ["onebox_site_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_companies_onebox_site", table_name="companies")
    op.drop_column("worklist_sync_states", "applied_at")
    op.drop_column("worklist_sync_states", "snapshot_version")
    op.drop_column("companies", "deactivated_at")
    op.drop_column("companies", "is_active")
    op.drop_column("companies", "onebox_site_id")
