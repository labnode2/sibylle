"""notifications: read_at, for the bell's list and its red dot

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    # What already left before this change is not "new": nothing lights the bell on day one.
    op.execute("UPDATE notifications SET read_at = now() WHERE account_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("notifications", "read_at")
