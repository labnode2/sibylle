"""discussion: the members tagged in a message, and its two notifications

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = "type IN ('new_prono', 'closing_soon', 'result', 'designation_reminder', 'report')"
_AFTER = (
    "type IN ('new_prono', 'closing_soon', 'result', 'designation_reminder', 'report',"
    " 'mention', 'discussion')"
)


# A switch without a row is on: the new types start on, on both channels, for everyone.
def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "mentions",
            postgresql.ARRAY(sa.Uuid()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.drop_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", type_="check")
    op.create_check_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", _AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM notification_prefs WHERE type IN ('mention', 'discussion')")
    op.drop_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", type_="check")
    op.create_check_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", _BEFORE)
    op.drop_column("messages", "mentions")
