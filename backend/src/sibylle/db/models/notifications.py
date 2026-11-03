import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from sibylle import clock
from sibylle.db.base import Base, new_id


class Notification(Base):
    """A message waiting to leave: written with the event that causes it, sent by the worker."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("state IN ('pending', 'sent', 'skipped', 'failed')", name="state"),
        Index("ix_notifications_state_next_attempt_at", "state", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    # NULL for an invitation sent to an address without an account: the address is payload["to"].
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organisations.id"))
    type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    dedupe_key: Mapped[str] = mapped_column(Text, unique=True)
    state: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    # The channels already done, so that a retry sends only what failed.
    done_channels: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )
    next_attempt_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    sent_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())


class NotificationPref(Base):
    """A switch turned off or back on; without a row, the type and channel are on."""

    __tablename__ = "notification_prefs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('new_prono', 'closing_soon', 'result', 'designation_reminder')", name="type"
        ),
        CheckConstraint("channel IN ('push', 'email')", name="channel"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    type: Mapped[str] = mapped_column(Text, primary_key=True)
    channel: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class PushSubscription(Base):
    """A device that accepted push notifications; removed when its push service forgets it."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    last_success_at: Mapped[datetime | None]
