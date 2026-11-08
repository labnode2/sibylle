"""invitations: the role the invited person gets on joining

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The invitations already there keep letting people in as readers.
def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column("role", sa.Text(), server_default="reader", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_invitations_role"), "invitations", "role IN ('reader', 'journalist', 'editor')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_invitations_role"), "invitations", type_="check")
    op.drop_column("invitations", "role")
