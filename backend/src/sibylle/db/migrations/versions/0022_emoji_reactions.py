"""reactions.kind: five new emojis replace the icons, the reactions given take the closest

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Each reaction already given becomes the new one closest in meaning, one for one, so no member
# ends up with the same kind twice on a prono. In the new display order.
RENAMED = {
    "bien_vu": "jackpot",
    "bravo": "yes",
    "rire": "enfin",
    "choc": "serieux",
    "doute": "malaise",
}


def _rename(renamed: dict[str, str]) -> None:
    op.drop_constraint(op.f("ck_reactions_kind"), "reactions", type_="check")
    cases = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in renamed.items())
    op.execute(f"UPDATE reactions SET kind = CASE kind {cases} END")
    kinds = ", ".join(f"'{new}'" for new in renamed.values())
    op.create_check_constraint(op.f("ck_reactions_kind"), "reactions", f"kind IN ({kinds})")


def upgrade() -> None:
    _rename(RENAMED)


def downgrade() -> None:
    _rename({new: old for old, new in RENAMED.items()})
