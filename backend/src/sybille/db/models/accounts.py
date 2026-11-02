import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from sybille import clock
from sybille.db.base import Base, new_id


class Account(Base):
    """A person. Name, first name and e-mail are never shown to another member."""

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("theme IN ('auto', 'light', 'dark')", name="theme"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    # NULL once the account is deleted.
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None]
    locale: Mapped[str] = mapped_column(Text, default="fr", server_default="fr")
    theme: Mapped[str] = mapped_column(Text, default="auto", server_default="auto")
    reduce_motion: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    deleted_at: Mapped[datetime | None]


class AuthSession(Base):
    """A signed-in browser: the cookie holds the token, the table only its digest."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    last_seen_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    expires_at: Mapped[datetime]
    user_agent: Mapped[str | None] = mapped_column(Text)


class EmailToken(Base):
    """A single-use link sent by e-mail: address check or password reset."""

    __tablename__ = "email_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('verify_email', 'reset_password')", name="purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
