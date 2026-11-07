"""collection: the base palette's colours an avatar no longer gets for free

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from sibylle.db.base import new_id
from sibylle.domain.pixels import COLORS

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# An avatar keeps the skin tones, ink, paper, red, indigo and gold for free
# (domain/pixels.AVATAR_INDICES); these 18 colours of the base palette are sold for avatars, at
# the colours' price. Logos and Pixel mystère drawings keep them all.
SOLD = (3, 5, 7, 8, 10, 11, 12, 16, 18, 20, 22, 23, 24, 25, 27, 29, 30, 31)
PRICE = 400
KEYS = [f"color-{index}" for index in SOLD]


def upgrade() -> None:
    catalog = sa.table(
        "catalog_items",
        sa.column("id", sa.Uuid()),
        sa.column("kind", sa.Text()),
        sa.column("key", sa.Text()),
        sa.column("name_key", sa.Text()),
        sa.column("price", sa.Integer()),
        sa.column("season", sa.Text()),
        sa.column("data", postgresql.JSONB()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        catalog,
        [
            {
                "id": new_id(),
                "kind": "color",
                "key": f"color-{index}",
                "name_key": f"catalog.color-{index}",
                "price": PRICE,
                "season": None,
                "data": {"index": index, "hex": COLORS[index]},
                "active": True,
            }
            for index in SOLD
        ],
    )


def downgrade() -> None:
    # The colours stay in the avatars that use them; their purchases and deals go.
    items = "SELECT id FROM catalog_items WHERE key IN :keys"
    for statement in (
        f"DELETE FROM weekly_deals WHERE item_id IN ({items})",
        f"DELETE FROM owned_items WHERE item_id IN ({items})",
        "DELETE FROM catalog_items WHERE key IN :keys",
    ):
        op.execute(sa.text(statement).bindparams(sa.bindparam("keys", KEYS, expanding=True)))
