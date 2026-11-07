"""Accounts and sessions: the account a Keycloak sign-in opens, signing out, deletion
(specs/002-keycloak-auth, research.md K6 and K7). Keycloak holds the passwords and sends the
e-mailed links; Sibylle copies the rest at each sign-in."""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.config import get_settings
from sibylle.db.models import (
    Account,
    AuthSession,
    Invitation,
    Membership,
    Message,
    Notification,
    NotificationPref,
    PushSubscription,
)
from sibylle.domain.content import DEFAULT_AVATAR
from sibylle.realtime import bus
from sibylle.services import keycloak, orgs
from sibylle.services.keycloak import Identity
from sibylle.services.security import new_token, token_hash

log = logging.getLogger(__name__)

SESSION_LIFETIME = timedelta(days=30)
# An unconfirmed address is read again in Keycloak at most this often (research.md K9).
IDENTITY_CHECK_EVERY = timedelta(minutes=1)


async def open_session(
    session: AsyncSession,
    account: Account,
    user_agent: str | None,
    *,
    keycloak_sid: str | None = None,
) -> str:
    """Signs a browser in; returns the token for its cookie. `keycloak_sid` is the Keycloak
    session opened by the same sign-in, closed with this one."""
    token = new_token()
    session.add(
        AuthSession(
            account_id=account.id,
            token_hash=token_hash(token),
            expires_at=clock.now() + SESSION_LIFETIME,
            user_agent=(user_agent or "")[:200] or None,
            keycloak_sid=keycloak_sid,
        )
    )
    return token


@dataclass(frozen=True)
class SignedIn:
    account: Account
    token: str
    # The sign-in made the account: its address check, if unconfirmed, is still to send.
    created: bool


async def sign_in(session: AsyncSession, identity: Identity, user_agent: str | None) -> SignedIn:
    """The account of the person Keycloak signed in, made at their first sign-in, and a new
    session's token. E-mail, names and the address check are copied from Keycloak each time;
    an address held by another live account stops the sign-in (`email_taken`): an account is
    tied by its Keycloak id, never by its address (research.md K6)."""
    account = await session.scalar(
        select(Account)
        .where(Account.keycloak_id == identity.sub, Account.deleted_at.is_(None))
        .with_for_update()
    )
    holder = await session.scalar(
        select(Account.id).where(Account.email == identity.email, Account.deleted_at.is_(None))
    )
    if holder is not None and (account is None or holder != account.id):
        raise AppError("email_taken")
    created = account is None
    if account is None:
        account = Account(keycloak_id=identity.sub)
        session.add(account)
    account.email = identity.email
    account.first_name = identity.first_name or None
    account.last_name = identity.last_name or None
    if not identity.email_verified:
        account.email_verified_at = None
    elif account.email_verified_at is None:
        account.email_verified_at = clock.now()
    await session.flush()
    token = await open_session(session, account, user_agent, keycloak_sid=identity.sid)
    return SignedIn(account, token, created)


async def logout(session: AsyncSession, token: str | None) -> str | None:
    """Closes the browser's session; returns the Keycloak session to close with it."""
    if not token:
        return None
    sid: str | None = await session.scalar(
        delete(AuthSession)
        .where(AuthSession.token_hash == token_hash(token))
        .returning(AuthSession.keycloak_sid)
    )
    return sid


async def end_sessions(session: AsyncSession, *where: ColumnElement[bool]) -> list[uuid.UUID]:
    """Ends the sessions that match `where` and closes their WebSockets (4401), once the
    transaction commits; returns their ids."""
    ended = list(
        (await session.scalars(delete(AuthSession).where(*where).returning(AuthSession.id))).all()
    )
    if ended:
        await bus.publish_signed_out(session, ended)
    return ended


async def end_keycloak_sessions(session: AsyncSession, logout: keycloak.Logout) -> list[uuid.UUID]:
    """The sessions a back-channel logout from Keycloak ends (research.md K8): those opened with
    its Keycloak session, or every session of its account when it names only the account."""
    where: list[ColumnElement[bool]] = []
    if logout.sub is not None:
        account = select(Account.id).where(Account.keycloak_id == logout.sub).scalar_subquery()
        where.append(AuthSession.account_id == account)
    if logout.sid is not None:
        where.append(AuthSession.keycloak_sid == logout.sid)
    return await end_sessions(session, *where) if where else []


def update_account(account: Account, changes: dict[str, Any]) -> None:
    """The account's own settings; names and e-mail change in Keycloak."""
    for field in ("theme", "reduce_motion", "locale"):
        if field in changes and changes[field] is not None:
            setattr(account, field, changes[field])


def verification_return() -> str:
    """Where the address check's link ends: back to the settings, through a sign-in that Keycloak
    passes at once (research.md K9)."""
    return f"{get_settings().public_origin}/api/auth/login?suite=/compte"


async def send_verification(account: Account) -> None:
    """Has Keycloak send the address check (research.md K9); IdentityUnavailable when it does not
    answer."""
    if account.keycloak_id is not None:
        await keycloak.send_verify_email(account.keycloak_id, verification_return())


async def send_first_verification(keycloak_id: uuid.UUID) -> None:
    """The address check of a new account, sent once its sign-in has answered (FR-008). Keycloak
    not sending it stops nobody: the settings send it again on demand."""
    try:
        await keycloak.send_verify_email(keycloak_id, verification_return())
    except keycloak.IdentityUnavailable:
        log.warning("address check not sent", extra={"keycloak_id": str(keycloak_id)})


async def refresh_identity(account: Account) -> None:
    """For an unconfirmed address: reads the account again in Keycloak, at most once a minute,
    and notes the address confirmed once Keycloak says so (FR-008), whichever device the link
    was followed on. Only the account's own address counts: a new one is copied, with its
    confirmation, at the next sign-in. Keycloak not answering changes nothing (SC-006)."""
    if account.email_verified_at is not None or account.keycloak_id is None:
        return
    now = clock.now()
    checked = account.identity_checked_at
    if checked is not None and now - checked < IDENTITY_CHECK_EVERY:
        return
    account.identity_checked_at = now
    try:
        user = await keycloak.get_user(account.keycloak_id)
    except keycloak.IdentityUnavailable:
        return
    if (
        user is not None
        and user.get("emailVerified") is True
        and str(user.get("email", "")).lower() == (account.email or "").lower()
    ):
        account.email_verified_at = now


ANONYMOUS_PSEUDO = "Ancien membre"


async def delete_account(
    session: AsyncSession, account: Account, *, current_token: str | None = None
) -> None:
    """Deletes an account (research.md R20): what identifies the person goes, their bets and
    ledger entries stay under « Ancien membre », so that past pots stay right for the others.
    Their messages go too, with their likes, since what they wrote may say who they are; their
    own likes stay, under « Ancien membre » (research.md J9).

    The newsroom's last editor names another first (`last_editor`, with its `org_id`); a
    newsroom whose only member this was goes with it.

    The account in Keycloak goes too, all or nothing (FR-013): once every change here is checked
    by the database, Keycloak deletes it, then the caller commits; Keycloak not answering
    (`identity_unavailable`) rolls everything back. The other devices' WebSockets close (4401);
    the browser of `current_token` leaves by itself.
    """
    keycloak_id = account.keycloak_id
    memberships = list(
        (
            await session.scalars(
                select(Membership)
                .where(Membership.account_id == account.id)
                .order_by(Membership.org_id)
            )
        ).all()
    )
    active = [member for member in memberships if member.status == "active"]
    # Every newsroom locked first, always in the same order, then every check before any change.
    for member in active:
        await orgs.lock_editors(session, member.org_id)
    others_stay = {member.id: await orgs.may_go(session, member) for member in active}

    await session.execute(
        delete(Message).where(Message.membership_id.in_([member.id for member in memberships]))
    )
    for member in memberships:
        member.pseudo = ANONYMOUS_PSEUDO
        member.avatar = DEFAULT_AVATAR
        member.avatar_frame_item_id = None
        member.showcase = []
        if member.status == "active":
            await orgs.depart(session, member, "anonymized")
            if not others_stay[member.id]:
                await orgs.close(session, member.org_id)
        else:
            member.status = "anonymized"

    email = account.email
    elsewhere = [AuthSession.account_id == account.id]
    if current_token:
        elsewhere.append(AuthSession.token_hash != token_hash(current_token))
    await end_sessions(session, *elsewhere)
    for table in (AuthSession, PushSubscription, NotificationPref, Notification):
        await session.execute(delete(table).where(table.account_id == account.id))
    if email:
        address = email.lower()
        await session.execute(delete(Invitation).where(func.lower(Invitation.email) == address))
        await session.execute(
            delete(Notification).where(func.lower(Notification.payload["to"].astext) == address)
        )
    account.keycloak_id = None
    account.email = None
    account.first_name = None
    account.last_name = None
    account.email_verified_at = None
    account.deleted_at = clock.now()
    await session.flush()
    if keycloak_id is not None:
        try:
            await keycloak.delete_user(keycloak_id)
        except keycloak.IdentityUnavailable as error:
            raise AppError("identity_unavailable") from error
