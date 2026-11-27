"""wordle: the word file's versions, each newsroom's word of the day, and its level

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wordle_lists",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wordle_lists")),
    )
    op.create_table(
        "wordle_days",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("word", sa.Text(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("word ~ '^[a-z]{5}$'", name=op.f("ck_wordle_days_word")),
        sa.CheckConstraint("level BETWEEN 1 AND 6", name=op.f("ck_wordle_days_level")),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organisations.id"], name=op.f("fk_wordle_days_org_id_organisations")
        ),
        sa.PrimaryKeyConstraint("org_id", "day", name=op.f("pk_wordle_days")),
    )
    # Normal for every newsroom until its editor chooses.
    op.add_column(
        "organisations",
        sa.Column("wordle_level", sa.Integer(), server_default="2", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_organisations_wordle_level"), "organisations", "wordle_level BETWEEN 1 AND 3"
    )


# The words drawn go with the tables: the game then gives the same word to every newsroom again.
def downgrade() -> None:
    op.drop_constraint(op.f("ck_organisations_wordle_level"), "organisations", type_="check")
    op.drop_column("organisations", "wordle_level")
    op.drop_table("wordle_days")
    op.drop_table("wordle_lists")
