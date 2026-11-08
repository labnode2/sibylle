import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from sibylle import clock
from sibylle.db.base import Base, new_id


class Account(Base):
    """A person. Name, first name and e-mail are never shown to another member. Keycloak holds
    the person's password and copies the rest here at each sign-in (specs/002-keycloak-auth)."""

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("theme IN ('auto', 'light', 'dark')", name="theme"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    # The `sub` of the account in Keycloak's realm, set when the first sign-in creates the
    # account. NULL once the account is deleted, and for the accounts of development databases
    # made before Keycloak.
    keycloak_id: Mapped[uuid.UUID | None] = mapped_column(unique=True)
    # NULL once the account is deleted.
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None]
    # The last time the account was read again in Keycloak while its address was unconfirmed
    # (at most once a minute).
    identity_checked_at: Mapped[datetime | None]
    locale: Mapped[str] = mapped_column(Text, default="fr", server_default="fr")
    theme: Mapped[str] = mapped_column(Text, default="light", server_default="light")
    reduce_motion: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # When the person closed the welcome pop-up that explains the game, shown in their first
    # newsroom; NULL until then.
    welcomed_at: Mapped[datetime | None]
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
    # The `sid` of the identity token: the Keycloak session opened at the same sign-in, closed
    # with this one. NULL for the sessions the tests open directly.
    keycloak_sid: Mapped[str | None] = mapped_column(Text, index=True)


class SignInAttempt(Base):
    """A sign-in under way through Keycloak, from `/api/auth/login` to `/api/auth/callback`
    (research.md K3). The `sibylle_signin` cookie holds its token, the table only the digest;
    single-use, for 10 minutes."""

    __tablename__ = "sign_in_attempts"
    __table_args__ = (CheckConstraint("action IN ('login', 'signup', 'password')", name="action"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    state: Mapped[str] = mapped_column(Text)
    nonce: Mapped[str] = mapped_column(Text)
    # The PKCE verifier: only its challenge goes along the browser.
    code_verifier: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    # The page of Sibylle to come back to, a path checked like the interface's `nextPath`.
    next_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
    expires_at: Mapped[datetime]
