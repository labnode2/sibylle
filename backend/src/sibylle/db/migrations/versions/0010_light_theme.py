"""light_theme: accounts start on the light theme instead of following the system

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("accounts", "theme", server_default="light")
    # No screen let anyone choose a theme before this revision: "auto" was only the default.
    op.execute("UPDATE accounts SET theme = 'light' WHERE theme = 'auto'")


def downgrade() -> None:
    op.alter_column("accounts", "theme", server_default="auto")
