"""game_schedule: the games of each planned week, and of an ordinary week from a Monday on

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _games_table(name: str, week_column: str) -> None:
    """Both tables: a newsroom, a Monday, and the games among the race and Pixel mystère."""
    op.create_table(
        name,
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column(week_column, sa.Date(), nullable=False),
        sa.Column("games", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"extract(isodow FROM {week_column}) = 1", name=op.f(f"ck_{name}_monday")
        ),
        sa.CheckConstraint(
            "games <@ ARRAY['runner', 'pixel']::text[]", name=op.f(f"ck_{name}_games")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organisations.id"], name=op.f(f"fk_{name}_org_id_organisations")
        ),
        sa.PrimaryKeyConstraint("org_id", week_column, name=op.f(f"pk_{name}")),
    )


def upgrade() -> None:
    # No row means nothing planned: every newsroom keeps both games, as before.
    _games_table("game_weeks", "week_start")
    _games_table("game_defaults", "from_week")


def downgrade() -> None:
    op.drop_table("game_defaults")
    op.drop_table("game_weeks")
