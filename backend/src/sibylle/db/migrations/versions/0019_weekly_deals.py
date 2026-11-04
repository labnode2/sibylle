"""weekly_deals: each newsroom's deal of the week in the collection

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weekly_deals",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("discount_pct", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "extract(isodow FROM week_start) = 1", name=op.f("ck_weekly_deals_monday")
        ),
        sa.CheckConstraint(
            "discount_pct IN (20, 30, 40, 50)", name=op.f("ck_weekly_deals_discount_pct")
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["catalog_items.id"], name=op.f("fk_weekly_deals_item_id_catalog_items")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organisations.id"], name=op.f("fk_weekly_deals_org_id_organisations")
        ),
        sa.PrimaryKeyConstraint("org_id", "week_start", name=op.f("pk_weekly_deals")),
    )


def downgrade() -> None:
    op.drop_table("weekly_deals")
