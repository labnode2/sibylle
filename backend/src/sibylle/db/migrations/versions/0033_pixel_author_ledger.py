"""ledger: the two kinds paid to the author of a Pixel mystère drawing

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = (
    "kind IN ('starting_balance', 'stake', 'base_gain', 'early_bird', 'pot_share', 'stake_lost',"
    " 'refund', 'reversal', 'purchase', 'minigame', 'adjustment', 'season_reset')"
)
_AFTER = _BEFORE[:-1] + ", 'pixel_author_bonus', 'pixel_author_find')"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", type_="check")
    op.create_check_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", _AFTER)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", type_="check")
    op.create_check_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", _BEFORE)
