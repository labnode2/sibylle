"""Ways into a newsroom: invitation links, nominative e-mail invitations and the access code."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.config import get_settings
from sibylle.db.models import Account, Invitation, Membership, Organisation
from sibylle.realtime import bus
from sibylle.services import notifications, orgs
from sibylle.services.security import new_token, token_hash

EMAIL_INVITATION_LIFETIME = timedelta(days=7)
LINK_MAX_LIFETIME = timedelta(days=90)


def join_url(token: str) -> str:
    return f"{get_settings().public_origin}/rejoindre/{token}"


def places_left(invitation: Invitation) -> int:
    return max(0, invitation.max_uses - invitation.use_count)


async def create_link(
    session: AsyncSession, author: Membership, *, max_uses: int, expires_at: datetime
) -> tuple[Invitation, str]:
    now = clock.now()
    if expires_at <= now or expires_at > now + LINK_MAX_LIFETIME:
        raise AppError("validation_error", {"expires_at": "out_of_range"})
    token = new_token()
    invitation = Invitation(
        org_id=author.org_id,
        kind="link",
        token_hash=token_hash(token),
        max_uses=max_uses,
        expires_at=expires_at,
        created_by=author.id,
    )
    session.add(invitation)
    await session.flush()
    return invitation, token


async def create_email_invitation(
    session: AsyncSession, author: Membership, org: Organisation, email: str
) -> Invitation:
    token = new_token()
    invitation = Invitation(
        org_id=org.id,
        kind="email",
        token_hash=token_hash(token),
        email=email.strip().lower(),
        max_uses=1,
        expires_at=clock.now() + EMAIL_INVITATION_LIFETIME,
        created_by=author.id,
    )
    session.add(invitation)
    await session.flush()
    await notifications.enqueue(
        session,
        type="invitation",
        org_id=org.id,
        dedupe_key=f"invitation:{invitation.id}",
        payload={
            "to": invitation.email,
            "inviter_pseudo": author.pseudo,
            "org_title": org.title,
            "link": join_url(token),
        },
    )
    return invitation


@dataclass
class Entry:
    org: Organisation
    invitation: Invitation | None


async def resolve(
    session: AsyncSession, *, token: str | None, code: str | None, lock: bool = False
) -> Entry:
    """The newsroom behind an invitation token or an access code, if it still lets people in."""
    if token:
        query = select(Invitation).where(Invitation.token_hash == token_hash(token))
        invitation = await session.scalar(query.with_for_update() if lock else query)
        if (
            invitation is None
            or invitation.revoked_at is not None
            or invitation.expires_at <= clock.now()
            or places_left(invitation) == 0
        ):
            raise AppError("invitation_invalid")
        org = await session.get(Organisation, invitation.org_id)
    elif code:
        invitation = None
        org = await session.scalar(
            select(Organisation).where(Organisation.access_code == code.strip().upper())
        )
    else:
        raise AppError("validation_error", {"token": "missing"})
    if org is None or org.deleted_at is not None:
        raise AppError("invitation_invalid")
    return Entry(org, invitation)


async def _membership(
    session: AsyncSession, org: Organisation, account: Account
) -> Membership | None:
    member: Membership | None = await session.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.account_id == account.id)
    )
    return member


async def preview(
    session: AsyncSession, account: Account, *, token: str | None, code: str | None
) -> dict[str, Any]:
    entry = await resolve(session, token=token, code=code)
    inviter = None
    if entry.invitation is not None:
        author = await session.get(Membership, entry.invitation.created_by)
        inviter = author.pseudo if author else None
    existing = await _membership(session, entry.org, account)
    return {
        "org": entry.org,
        "member_count": await orgs.member_count(session, entry.org.id),
        "places_left": places_left(entry.invitation) if entry.invitation else None,
        "invited_by_pseudo": inviter,
        "charter": entry.org.charter,
        "already_member": existing is not None and existing.status == "active",
    }


async def join(
    session: AsyncSession,
    account: Account,
    *,
    token: str | None,
    code: str | None,
    pseudo: str,
    avatar: dict[str, Any],
) -> tuple[Organisation, Membership]:
    entry = await resolve(session, token=token, code=code, lock=True)
    existing = await _membership(session, entry.org, account)
    if existing is not None and existing.status != "left":
        raise AppError("invalid_state")
    if existing is not None:
        # A former member comes back with their pseudo, avatar and history (FR-123).
        existing.status = "active"
        existing.left_at = None
        existing.charter_accepted_at = clock.now()
        member = existing
    else:
        member = await orgs.add_member(
            session, entry.org, account, role="reader", pseudo=pseudo, avatar=avatar
        )
    if entry.invitation is not None:
        entry.invitation.use_count += 1
    await session.flush()
    await bus.publish(
        session,
        "member.joined",
        {"member": orgs.public_member(member)},
        topics=[f"org:{entry.org.id}"],
    )
    return entry.org, member
