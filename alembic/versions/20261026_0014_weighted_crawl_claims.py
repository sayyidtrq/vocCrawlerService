"""Add tenant weights and the tenant crawl-queue index."""

import sqlalchemy as sa

from alembic import op

revision = "20261026_0014"
down_revision = "20261022_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(
            sa.Column("weight", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_check_constraint("ck_companies_weight_positive", "weight > 0")
    op.create_index(
        "idx_crawl_jobs_company_claim",
        "crawl_jobs",
        ["company_id", "status", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_crawl_jobs_company_claim", table_name="crawl_jobs")
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_constraint("ck_companies_weight_positive", type_="check")
        batch_op.drop_column("weight")
