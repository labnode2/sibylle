"""Dependencies shared by the routes: database session, signed-in account, member and role."""

import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.config import get_settings
from sibylle.db.models import Account, AuthSession, Membership, Organisation
from sibylle.db.session import transaction
from sibylle.domain.permissions import Action, can
from sibylle.services import accounts, keycloak
from sibylle.services.accounts import SESSION_LIFETIME
from sibylle.services.security import token_hash

log = logging.getLogger(__name__)

SESSION_COOKIE = "sibylle_session"
# A session's expiry slides forward at most once an hour, to spare a write on every request; the
# account is then read again in Keycloak (research.md K15).
TOUCH_EVERY = timedelta(hours=1)


def clear_session_cookie(response: Response) -> None:
    """Removes the session cookie, with the attributes it was set with."""
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=get_settings().secure_cookies,
        httponly=True,
        samesite="lax",
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """One transaction per request: committed before the response, rolled back on error."""
    async with transaction() as session:
        yield session


# "function" scope: the commit happens before the response leaves. With the default "request"
# scope FastAPI would commit after sending it, and a client acting on the response (opening the
# WebSocket right after signing up, say) could miss the request's writes.
Db = Annotated[AsyncSession, Depends(get_db, scope="function")]


async def _still_in_keycloak(account: Account) -> bool:
    """The account still exists and is enabled in Keycloak, which says nothing when an
    administrator disables or deletes one (research.md K15). Keycloak not answering keeps the
    session (SC-006); an account made before Keycloak has nothing to read."""
    if account.keycloak_id is None:
        return True
    try:
        user = await keycloak.get_user(account.keycloak_id)
    except keycloak.IdentityUnavailable:
        log.warning("account not read again in keycloak", extra={"account_id": str(account.id)})
        return True
    return user is not None and user.get("enabled") is not False


async def session_from_token(
    session: AsyncSession, token: str | None
) -> tuple[Account, AuthSession] | None:
    """The account and the session of a cookie's token, if it is signed in. The session slides
    forward once an hour, after the account was read again in Keycloak: gone or disabled there,
    every session of the account ends, and the token signs nobody in."""
    if not token:
        return None
    auth = await session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash(token))
    )
    now = clock.now()
    if auth is None or auth.expires_at <= now:
        return None
    account = await session.get(Account, auth.account_id)
    if account is None or account.deleted_at is not None:
        return None
    if now - auth.last_seen_at >= TOUCH_EVERY:
        if not await _still_in_keycloak(account):
            # In a transaction of its own: the request's rolls back once it answers 401.
            async with transaction() as ending:
                await accounts.end_sessions(ending, AuthSession.account_id == account.id)
            log.info("signed out by keycloak", extra={"account_id": str(account.id)})
            return None
        auth.last_seen_at = now
        auth.expires_at = now + SESSION_LIFETIME
    return account, auth


async def account_from_token(session: AsyncSession, token: str | None) -> Account | None:
    signed_in = await session_from_token(session, token)
    return signed_in[0] if signed_in else None


async def current_account(request: Request, session: Db) -> Account:
    account = await account_from_token(session, request.cookies.get(SESSION_COOKIE))
    if account is None:
        raise AppError("not_authenticated")
    return account


CurrentAccount = Annotated[Account, Depends(current_account)]


async def member_of(
    session: AsyncSession, org_id: uuid.UUID, account_id: uuid.UUID
) -> Membership | None:
    """The account's active membership in a newsroom that still exists."""
    member: Membership | None = await session.scalar(
        select(Membership)
        .join(Organisation, Organisation.id == Membership.org_id)
        .where(
            Membership.org_id == org_id,
            Membership.account_id == account_id,
            Membership.status == "active",
            Organisation.deleted_at.is_(None),
        )
    )
    return member


async def current_member(org_id: uuid.UUID, account: CurrentAccount, session: Db) -> Membership:
    """A newsroom you are not a member of answers 404, so its existence stays private."""
    member = await member_of(session, org_id, account.id)
    if member is None:
        raise AppError("not_found")
    return member


CurrentMember = Annotated[Membership, Depends(current_member)]


def require(action: Action) -> Callable[..., Awaitable[Membership]]:
    """A member whose role allows the action, or 403."""

    async def check(member: CurrentMember) -> Membership:
        if not can(member.role, action):
            raise AppError("forbidden")
        return member

    return check


class RateLimiter:
    """At most `limit` hits per key over a sliding window, in this process's memory."""

    def __init__(self, limit: int, window: timedelta) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)

    def check(self, *keys: str) -> None:
        """429 when one of the keys already used up its hits in the window."""
        now = clock.now()
        for key in keys:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise AppError("rate_limited")

    def add(self, *keys: str) -> None:
        now = clock.now()
        for key in keys:
            self._hits[key].append(now)

    def hit(self, *keys: str) -> None:
        self.check(*keys)
        self.add(*keys)

    def reset(self, *keys: str) -> None:
        for key in keys:
            self._hits.pop(key, None)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@dataclass
class Limits:
    """The rate limits of one API process."""

    # Keycloak limits the sign-ins and the reset requests (specs/002-keycloak-auth); Sibylle, the
    # address checks it asks Keycloak to send.
    resend_verification: RateLimiter = field(
        default_factory=lambda: RateLimiter(3, timedelta(hours=1))
    )
    # Joining is limited per account, against guessing access codes, and much more loosely per
    # address: a whole office may join from behind one.
    join: RateLimiter = field(default_factory=lambda: RateLimiter(10, timedelta(hours=1)))
    join_ip: RateLimiter = field(default_factory=lambda: RateLimiter(300, timedelta(hours=1)))
    secret_code: RateLimiter = field(default_factory=lambda: RateLimiter(5, timedelta(hours=1)))
    # Public press cards are read without an account, often from another site's iframe: loosely
    # per IP, since a whole office may open a page that shows several of them.
    public_card: RateLimiter = field(
        default_factory=lambda: RateLimiter(600, timedelta(minutes=10))
    )


def limits(request: Request) -> Limits:
    found: Limits = request.app.state.limits
    return found
