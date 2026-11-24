"""Scope location and review identities per tenant.

Revision ID: 20260929_0010
Revises: d794f4a71861
"""

from alembic import op

revision = "20260929_0010"
down_revision = "d794f4a71861"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_locations_source_place", "locations", type_="unique")
    op.create_unique_constraint(
        "uq_locations_company_source_place",
        "locations",
        ["company_id", "source", "external_place_id"],
    )
    op.drop_constraint("reviews_review_hash_key", "reviews", type_="unique")
    op.create_unique_constraint(
        "uq_reviews_company_hash", "reviews", ["company_id", "review_hash"]
    )
    op.drop_constraint(
        "competitor_reviews_review_hash_key", "competitor_reviews", type_="unique"
    )
    op.create_unique_constraint(
        "uq_comp_reviews_competitor_hash",
        "competitor_reviews",
        ["competitor_id", "review_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_comp_reviews_competitor_hash", "competitor_reviews", type_="unique"
    )
    op.create_unique_constraint(
        "competitor_reviews_review_hash_key", "competitor_reviews", ["review_hash"]
    )
    op.drop_constraint("uq_reviews_company_hash", "reviews", type_="unique")
    op.create_unique_constraint("reviews_review_hash_key", "reviews", ["review_hash"])
    op.drop_constraint(
        "uq_locations_company_source_place", "locations", type_="unique"
    )
    op.create_unique_constraint(
        "uq_locations_source_place", "locations", ["source", "external_place_id"]
    )
