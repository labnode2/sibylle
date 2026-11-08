import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sibylle import clock
from sibylle.db.base import Base, new_id
from sibylle.db.models.collection import CatalogItem
from sibylle.domain.content import DEFAULT_LOGO


class Organisation(Base):
    """A newsroom (rédaction): closed, with its own members, pronos and laurels settings."""

    __tablename__ = "organisations"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 40", name="title_length"),
        # Never JSON null either: a newsroom always shows a drawing.
        CheckConstraint("jsonb_typeof(logo) = 'object'", name="logo"),
        CheckConstraint("starting_balance >= 0", name="starting_balance"),
        CheckConstraint("max_base_gain >= 0", name="max_base_gain"),
        CheckConstraint("early_bird_pct BETWEEN 0 AND 100", name="early_bird_pct"),
        CheckConstraint("early_bird_count >= 0", name="early_bird_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text)
    # Never empty: the default logo until the editor chooses or draws another.
    logo: Mapped[dict[str, Any]] = mapped_column(default=lambda: dict(DEFAULT_LOGO))
    background_key: Mapped[str] = mapped_column(Text)
    # NULL when the access code is turned off.
    access_code: Mapped[str | None] = mapped_column(Text, unique=True)
    starting_balance: Mapped[int] = mapped_column(default=100, server_default="100")
    max_base_gain: Mapped[int] = mapped_column(default=50, server_default="50")
    early_bird_pct: Mapped[int] = mapped_column(default=20, server_default="20")
    early_bird_count: Mapped[int] = mapped_column(default=5, server_default="5")
    editor_note: Mapped[str | None] = mapped_column(Text)
    charter: Mapped[str] = mapped_column(Text)
    # The number of the newsroom's last prono; the next one takes the following number.
    last_prono_number: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    deleted_at: Mapped[datetime | None]


class Membership(Base):
    """An account inside a newsroom: role, pseudo, avatar and laurels are per newsroom."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "account_id"),
        CheckConstraint("role IN ('reader', 'journalist', 'editor')", name="role"),
        CheckConstraint("status IN ('active', 'left', 'anonymized')", name="status"),
        CheckConstraint("coins >= 0", name="coins"),
        CheckConstraint("char_length(pseudo) BETWEEN 2 AND 24", name="pseudo_length"),
        # A pseudo is unique in its newsroom, whatever its case, among active and departed members.
        Index(
            "uq_memberships_org_id_pseudo",
            "org_id",
            text("lower(pseudo)"),
            unique=True,
            postgresql_where=text("status IN ('active', 'left')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    role: Mapped[str] = mapped_column(Text, default="reader", server_default="reader")
    status: Mapped[str] = mapped_column(Text, default="active", server_default="active")
    pseudo: Mapped[str] = mapped_column(Text)
    avatar: Mapped[dict[str, Any]]
    avatar_frame_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("catalog_items.id"))
    # An animation of the collection around the avatar, worn with or without a frame.
    avatar_animation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_items.id")
    )
    # Up to three things shown on the press card, in order: {"kind": "item" | "trophy", "id"}.
    showcase: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    # Loaded with the member, so that every screen can show the frame and the animation.
    avatar_frame: Mapped[CatalogItem | None] = relationship(
        lazy="selectin", foreign_keys=[avatar_frame_item_id]
    )
    avatar_animation: Mapped[CatalogItem | None] = relationship(
        lazy="selectin", foreign_keys=[avatar_animation_item_id]
    )
    # The press card seen from outside, without an account (US15): private until the member
    # makes it public. Its address is drawn the first time and kept, so that a link or an iframe
    # shows the card again when it goes public again.
    card_public: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    card_token: Mapped[str | None] = mapped_column(Text, unique=True)
    # Caches of the ledger, updated in the same transaction as each entry.
    balance: Mapped[int] = mapped_column(default=0, server_default="0")
    season_score: Mapped[int] = mapped_column(default=0, server_default="0")
    # Cache of coin_entries, and the last Monday whose conversion the member was told about.
    coins: Mapped[int] = mapped_column(default=0, server_default="0")
    coins_seen_week: Mapped[date | None]
    joined_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    charter_accepted_at: Mapped[datetime | None]
    left_at: Mapped[datetime | None]

    @property
    def frame(self) -> str | None:
        """The key of the avatar's frame, if the member chose one."""
        return self.avatar_frame.key if self.avatar_frame else None

    @property
    def animation(self) -> str | None:
        """The key of the animation around the avatar, if the member chose one."""
        return self.avatar_animation.key if self.avatar_animation else None


class Invitation(Base):
    """A way into a newsroom: a link with a number of places, or a single-use e-mail invitation;
    either one lets people in with the role the editor chose."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("kind IN ('link', 'email')", name="kind"),
        CheckConstraint("max_uses >= 1", name="max_uses"),
        CheckConstraint("kind = 'link' OR (email IS NOT NULL AND max_uses = 1)", name="email_kind"),
        CheckConstraint("role IN ('reader', 'journalist', 'editor')", name="role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="reader", server_default="reader")
    max_uses: Mapped[int]
    use_count: Mapped[int] = mapped_column(default=0, server_default="0")
    expires_at: Mapped[datetime]
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
