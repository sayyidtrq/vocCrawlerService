"""Tambah dimensi kompetitor pada antrean crawl durable.

Perubahan ini ADITIF dan MELONGGARKAN saja:
- crawl_jobs.location_id dan crawl_jobs.onebox_location_id menjadi nullable
- kolom baru crawl_jobs.competitor_id (FK ke competitors)
- partial unique index agar satu kompetitor tidak dobel dalam satu batch

Constraint lama uq_crawl_jobs_batch_location sengaja TIDAK dihapus. Di
PostgreSQL dua NULL dianggap berbeda, sehingga baris kompetitor (location_id
NULL) tidak saling bentrok di constraint itu, sementara baris cabang tetap
dijaga persis seperti sebelumnya.

Karena hanya melonggarkan, kode versi lama yang selalu mengisi location_id dan
onebox_location_id tetap berjalan tanpa perubahan apa pun.

Revision ID: 20260805_0005
Revises: 20260804_0004
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0005"
down_revision = "20260804_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "crawl_jobs", "location_id", existing_type=sa.Integer(), nullable=True
    )
    op.alter_column(
        "crawl_jobs", "onebox_location_id", existing_type=sa.Integer(), nullable=True
    )
    op.add_column(
        "crawl_jobs", sa.Column("competitor_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_crawl_jobs_competitor_id",
        "crawl_jobs",
        "competitors",
        ["competitor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_crawl_jobs_competitor", "crawl_jobs", ["competitor_id"])
    op.create_index(
        "uq_crawl_jobs_batch_competitor",
        "crawl_jobs",
        ["batch_id", "competitor_id"],
        unique=True,
        postgresql_where=sa.text("competitor_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Baris kompetitor harus dibuang lebih dulu: kolom lama tidak bisa
    # dikembalikan ke NOT NULL selama masih ada job kompetitor yang
    # location_id-nya NULL.
    op.execute("DELETE FROM crawl_jobs WHERE competitor_id IS NOT NULL")
    op.drop_index("uq_crawl_jobs_batch_competitor", table_name="crawl_jobs")
    op.drop_index("idx_crawl_jobs_competitor", table_name="crawl_jobs")
    op.drop_constraint(
        "fk_crawl_jobs_competitor_id", "crawl_jobs", type_="foreignkey"
    )
    op.drop_column("crawl_jobs", "competitor_id")
    op.alter_column(
        "crawl_jobs", "onebox_location_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "crawl_jobs", "location_id", existing_type=sa.Integer(), nullable=False
    )
