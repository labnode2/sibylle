"""wordle: a member's game of the day

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wordle_games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("guesses", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("state", sa.Text(), server_default="playing", nullable=False),
        sa.Column("laurels", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('playing', 'won', 'lost')", name=op.f("ck_wordle_games_state")
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_wordle_games_membership_id_memberships"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organisations.id"], name=op.f("fk_wordle_games_org_id_organisations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wordle_games")),
        sa.UniqueConstraint("membership_id", "day", name=op.f("uq_wordle_games_membership_id_day")),
    )
    op.create_index("ix_wordle_games_org_id_day", "wordle_games", ["org_id", "day"])


def downgrade() -> None:
    op.drop_index("ix_wordle_games_org_id_day", table_name="wordle_games")
    op.drop_table("wordle_games")
