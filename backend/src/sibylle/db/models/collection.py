import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from sibylle import clock
from sibylle.db.base import Base, new_id


class CatalogItem(Base):
    """An object of the collection, the same for every newsroom: a crystal ball, a colour of the
    pixel editor or an avatar frame. Without a price, it only comes from a secret code."""

    __tablename__ = "catalog_items"
    __table_args__ = (
        CheckConstraint("kind IN ('ball', 'color', 'frame')", name="kind"),
        CheckConstraint("price IS NULL OR price > 0", name="price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(Text, unique=True)
    name_key: Mapped[str] = mapped_column(Text)
    price: Mapped[int | None]
    # The season of a seasonal ball.
    season: Mapped[str | None] = mapped_column(Text)
    # A ball's variant of the crystal ball kit, a colour's palette index, a frame's style.
    data: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'"))
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class OwnedItem(Base):
    __tablename__ = "owned_items"
    __table_args__ = (
        UniqueConstraint("membership_id", "item_id"),
        CheckConstraint("source IN ('purchase', 'secret_code')", name="source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_items.id"))
    source: Mapped[str] = mapped_column(Text)
    acquired_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class SecretCode(Base):
    """A code that unlocks a surprise. Only its fingerprint is stored."""

    __tablename__ = "secret_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    code_hash: Mapped[str] = mapped_column(Text, unique=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_items.id"))
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class SecretCodeRedemption(Base):
    """A member used a code: once per member."""

    __tablename__ = "secret_code_redemptions"
    __table_args__ = (UniqueConstraint("secret_code_id", "membership_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    secret_code_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("secret_codes.id"))
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    redeemed_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
