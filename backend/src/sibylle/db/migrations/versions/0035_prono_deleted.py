"""pronos: deleted_at and deleted_by, a cancelled prono deleted from the lists

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pronos", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pronos", sa.Column("deleted_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_pronos_deleted_by_memberships"), "pronos", "memberships", ["deleted_by"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_pronos_deleted_by_memberships"), "pronos", type_="foreignkey")
    op.drop_column("pronos", "deleted_by")
    op.drop_column("pronos", "deleted_at")
