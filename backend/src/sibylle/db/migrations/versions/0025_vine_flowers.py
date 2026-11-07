"""collection: the vine and flower frames, and the flowers animation

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from sibylle.db.base import new_id

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The collection lists the objects of a kind by their `index`, then their key: by price here.
# The plain frames have no index; the vine and flower frames come after them, then the gold
# frame (its index goes from 1 to 3). The flowers come after the other animations.
ITEMS = [
    ("frame", "frame-vine", 2500, {"style": "vine", "index": 1}),
    ("frame", "frame-flowers", 3000, {"style": "flowers", "index": 2}),
    ("animation", "animation-flowers", 2500, {"style": "flowers", "index": 3}),
]
KEYS = [key for _, key, _, _ in ITEMS]


def _gold_index(index: int) -> None:
    op.execute(
        sa.text(
            "UPDATE catalog_items SET data = jsonb_set(data, '{index}', to_jsonb(CAST(:index AS int)))"
            " WHERE key = 'frame-gold'"
        ).bindparams(index=index)
    )


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
                "kind": kind,
                "key": key,
                "name_key": f"catalog.{key}",
                "price": price,
                "season": None,
                "data": data,
                "active": True,
            }
            for kind, key, price, data in ITEMS
        ],
    )
    _gold_index(3)


def downgrade() -> None:
    _gold_index(1)
    # What refers to the new items goes with them; a showcase keeps a dangling reference,
    # which the press card already skips.
    items = "SELECT id FROM catalog_items WHERE key IN :keys"
    for statement in (
        f"UPDATE memberships SET avatar_frame_item_id = NULL WHERE avatar_frame_item_id IN ({items})",
        "UPDATE memberships SET avatar_animation_item_id = NULL"
        f" WHERE avatar_animation_item_id IN ({items})",
        f"DELETE FROM weekly_deals WHERE item_id IN ({items})",
        f"DELETE FROM owned_items WHERE item_id IN ({items})",
        "DELETE FROM catalog_items WHERE key IN :keys",
    ):
        op.execute(sa.text(statement).bindparams(sa.bindparam("keys", KEYS, expanding=True)))
