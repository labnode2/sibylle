"""accounts: when the welcome pop-up that explains the game was closed

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Left NULL for the accounts already there: they see the pop-up once too.
def upgrade() -> None:
    op.add_column("accounts", sa.Column("welcomed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("accounts", "welcomed_at")
