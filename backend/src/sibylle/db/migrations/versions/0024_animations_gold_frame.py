"""collection: profile animations, worn beside a frame, and the gold frame

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from sibylle.db.base import new_id

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The animations around the avatar, from 1,200 coins, and the gold frame at 10,000. The
# collection lists the objects of a kind by their `index`, then their key: here, by price.
ANIMATIONS = {"sun": 1200, "shine": 1500, "sparkles": 2000}
GOLD_FRAME_PRICE = 10_000
KEYS = [*(f"animation-{a}" for a in ANIMATIONS), "frame-gold"]


def _items() -> list[dict[str, object]]:
    def item(kind: str, key: str, price: int, data: dict[str, object]) -> dict[str, object]:
        return {
            "id": new_id(),
            "kind": kind,
            "key": key,
            "name_key": f"catalog.{key}",
            "price": price,
            "season": None,
            "data": data,
            "active": True,
        }

    return [
        *(
            item("animation", f"animation-{a}", price, {"style": a, "index": index})
            for index, (a, price) in enumerate(ANIMATIONS.items())
        ),
        # After the other frames, which have no index.
        item("frame", "frame-gold", GOLD_FRAME_PRICE, {"style": "gold", "index": 1}),
    ]


def upgrade() -> None:
    op.drop_constraint(op.f("ck_catalog_items_kind"), "catalog_items", type_="check")
    op.create_check_constraint(
        op.f("ck_catalog_items_kind"),
        "catalog_items",
        "kind IN ('ball', 'color', 'frame', 'animation')",
    )
    op.add_column("memberships", sa.Column("avatar_animation_item_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_memberships_avatar_animation_item_id_catalog_items"),
        "memberships",
        "catalog_items",
        ["avatar_animation_item_id"],
        ["id"],
    )
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
    op.bulk_insert(catalog, _items())


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_memberships_avatar_animation_item_id_catalog_items"),
        "memberships",
        type_="foreignkey",
    )
    op.drop_column("memberships", "avatar_animation_item_id")
    # What refers to the new items goes with them; a showcase keeps a dangling reference,
    # which the press card already skips.
    items = "SELECT id FROM catalog_items WHERE key IN :keys"
    for statement in (
        f"UPDATE memberships SET avatar_frame_item_id = NULL WHERE avatar_frame_item_id IN ({items})",
        f"DELETE FROM weekly_deals WHERE item_id IN ({items})",
        f"DELETE FROM owned_items WHERE item_id IN ({items})",
        "DELETE FROM catalog_items WHERE key IN :keys",
    ):
        op.execute(sa.text(statement).bindparams(sa.bindparam("keys", KEYS, expanding=True)))
    op.drop_constraint(op.f("ck_catalog_items_kind"), "catalog_items", type_="check")
    op.create_check_constraint(
        op.f("ck_catalog_items_kind"), "catalog_items", "kind IN ('ball', 'color', 'frame')"
    )
