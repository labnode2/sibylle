"""notifications: « Nouveau signalement », for whoever handles the reports

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = "type IN ('new_prono', 'closing_soon', 'result', 'designation_reminder')"
_AFTER = "type IN ('new_prono', 'closing_soon', 'result', 'designation_reminder', 'report')"


# A switch without a row is on: the new type starts on, on both channels, for everyone.
def upgrade() -> None:
    op.drop_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", type_="check")
    op.create_check_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", _AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM notification_prefs WHERE type = 'report'")
    op.drop_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", type_="check")
    op.create_check_constraint(op.f("ck_notification_prefs_type"), "notification_prefs", _BEFORE)
