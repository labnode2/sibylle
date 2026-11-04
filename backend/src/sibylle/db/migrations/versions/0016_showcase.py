"""showcase: up to three objects or trophies on the press card; the balls leave the shop

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column(
            "showcase",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    # The balls are no longer sold: a season's engraved ball and the secret codes bring them.
    # The balls already bought stay in their owners' collections.
    op.execute("UPDATE catalog_items SET price = NULL WHERE kind = 'ball'")


def downgrade() -> None:
    op.execute("UPDATE catalog_items SET price = 800 WHERE kind = 'ball' AND season IS NOT NULL")
    op.drop_column("memberships", "showcase")
