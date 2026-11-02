"""base: citext and the seasons from autumn 2026 to 2030

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from sybille.domain.seasons import SeasonKey, season_bounds, seasons_between

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    seasons = op.create_table(
        "seasons",
        sa.Column("id", sa.SmallInteger(), sa.Identity(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "name IN ('spring', 'summer', 'autumn', 'winter')", name=op.f("ck_seasons_name")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seasons")),
        sa.UniqueConstraint("year", "name", name=op.f("uq_seasons_year_name")),
    )
    rows = []
    for key in seasons_between(SeasonKey(2026, "autumn"), SeasonKey(2030, "winter")):
        starts_at, ends_at = season_bounds(key.year, key.name)
        rows.append(
            {"year": key.year, "name": key.name, "starts_at": starts_at, "ends_at": ends_at}
        )
    op.bulk_insert(seasons, rows)


def downgrade() -> None:
    op.drop_table("seasons")
