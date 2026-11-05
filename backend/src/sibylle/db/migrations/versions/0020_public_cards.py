"""memberships.card_public and card_token: a press card anyone may see with its link

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column("card_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("memberships", sa.Column("card_token", sa.Text(), nullable=True))
    op.create_unique_constraint(op.f("uq_memberships_card_token"), "memberships", ["card_token"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_memberships_card_token"), "memberships", type_="unique")
    op.drop_column("memberships", "card_token")
    op.drop_column("memberships", "card_public")
