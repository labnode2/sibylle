"""wordle: when each game ended, for the ranking of the day, and the chain's bonus of a win

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("wordle_games", sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.add_column("wordle_games", sa.Column("streak_bonus", sa.Integer()))
    # Nobody kept when the games already over ended: the time of their first try stands in. The
    # games won before the chain of wins paid no bonus.
    op.execute("UPDATE wordle_games SET finished_at = created_at WHERE state <> 'playing'")
    op.execute("UPDATE wordle_games SET streak_bonus = 0 WHERE state = 'won'")
    op.create_check_constraint(
        op.f("ck_wordle_games_finished"),
        "wordle_games",
        "(state = 'playing') = (finished_at IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_wordle_games_finished"), "wordle_games", type_="check")
    op.drop_column("wordle_games", "streak_bonus")
    op.drop_column("wordle_games", "finished_at")
