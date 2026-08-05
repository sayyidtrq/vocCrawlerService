"""tambah urutan pengambilan pada crawl_jobs

Google Maps tidak menyediakan penyaring tanggal, hanya empat urutan. Urutan
karena itu bukan sekadar preferensi tampilan — ia menentukan apakah rentang
tanggal bisa dikerjakan sama sekali, sebab berhenti-awal hanya sah pada daftar
yang kronologis.

Revision ID: 20260804_0004
Revises: 20260803_0003
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260804_0004"
down_revision = "20260803_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crawl_jobs",
        sa.Column("sort_by", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crawl_jobs", "sort_by")
