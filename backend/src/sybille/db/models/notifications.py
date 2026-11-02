import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from sybille import clock
from sybille.db.base import Base, new_id


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
    next_attempt_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    sent_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
