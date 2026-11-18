"""settlements: 'result_cancellation', a result taken back without cancelling the prono

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = "kind IN ('resolution', 'correction', 'cancellation')"
_AFTER = "kind IN ('resolution', 'correction', 'cancellation', 'result_cancellation')"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_settlements_kind"), "settlements", type_="check")
    op.create_check_constraint(op.f("ck_settlements_kind"), "settlements", _AFTER)


# Only before any result was cancelled: those settlements and their reversals stay in the ledger.
def downgrade() -> None:
    op.drop_constraint(op.f("ck_settlements_kind"), "settlements", type_="check")
    op.create_check_constraint(op.f("ck_settlements_kind"), "settlements", _BEFORE)
