"""Newsrooms and their members."""

import secrets
import unicodedata
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sybille import clock
from sybille.api.errors import AppError
from sybille.db.models import Account, Membership, Organisation, Section
from sybille.domain.content import BACKGROUND_KEYS, DEFAULT_CHARTER
from sybille.domain.ledger import starting_balance
from sybille.domain.pixels import PixelImageError, validate_pixel_image
from sybille.realtime import bus
from sybille.services import ledger

ACCESS_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
DEFAULT_SECTION = "Général"
_VISIBLE = ("active", "left")


def code_prefix(title: str) -> str:
    """Up to six capital letters of the title, accents removed: « Sophia Office » → SOPHIA."""
    letters = [c for c in unicodedata.normalize("NFKD", title).upper() if "A" <= c <= "Z"]
    return "".join(letters[:6]) or "REDAC"


async def new_access_code(session: AsyncSession, title: str) -> str:
    prefix = code_prefix(title)
    while True:
        suffix = "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(3))
        code = f"{prefix}-{suffix}"
        taken = await session.scalar(
            select(Organisation.id).where(Organisation.access_code == code)
        )
        if taken is None:
            return code


def checked_drawing(
    field: str, data: dict[str, Any], unlocked: set[int] | None = None
) -> dict[str, Any]:
    try:
        return validate_pixel_image(data, unlocked or set())
    except PixelImageError as error:
        raise AppError("validation_error", {field: "invalid"}) from error


async def pseudo_taken(
    session: AsyncSession, org_id: uuid.UUID, pseudo: str, *, except_member: uuid.UUID | None = None
) -> bool:
    query = select(Membership.id).where(
        Membership.org_id == org_id,
        func.lower(Membership.pseudo) == pseudo.lower(),
        Membership.status.in_(_VISIBLE),
    )
    if except_member is not None:
        query = query.where(Membership.id != except_member)
    return await session.scalar(query) is not None


def public_member(member: Membership) -> dict[str, Any]:
    """What every member may see of another: never a name, a first name or an e-mail."""
    return {
        "id": str(member.id),
        "pseudo": member.pseudo,
        "avatar": member.avatar,
        "frame": None,
        "role": member.role,
        "joined_at": member.joined_at.isoformat(),
    }


async def add_member(
    session: AsyncSession,
    org: Organisation,
    account: Account,
    *,
    role: str,
    pseudo: str,
    avatar: dict[str, Any],
) -> Membership:
    """A new member with the newsroom's starting balance."""
    if await pseudo_taken(session, org.id, pseudo):
        raise AppError("pseudo_taken")
    member = Membership(
        org_id=org.id,
        account_id=account.id,
        role=role,
        pseudo=pseudo,
        avatar=checked_drawing("avatar", avatar),
        charter_accepted_at=clock.now(),
    )
    session.add(member)
    await session.flush()
    await ledger.append(session, member.id, starting_balance(org.starting_balance))
    return member


async def create_org(
    session: AsyncSession,
    account: Account,
    *,
    title: str,
    background_key: str,
    logo: dict[str, Any] | None,
    pseudo: str,
    avatar: dict[str, Any],
) -> tuple[Organisation, Membership]:
    if background_key not in BACKGROUND_KEYS:
        raise AppError("validation_error", {"background_key": "unknown"})
    org = Organisation(
        title=title,
        background_key=background_key,
        logo=checked_drawing("logo", logo) if logo else None,
        charter=DEFAULT_CHARTER,
        access_code=await new_access_code(session, title),
    )
    session.add(org)
    await session.flush()
    session.add(Section(org_id=org.id, name=DEFAULT_SECTION, position=0))
    member = await add_member(session, org, account, role="editor", pseudo=pseudo, avatar=avatar)
    return org, member


async def active_members(session: AsyncSession, org_id: uuid.UUID) -> list[Membership]:
    return list(
        (
            await session.scalars(
                select(Membership)
                .where(Membership.org_id == org_id, Membership.status == "active")
                .order_by(Membership.joined_at)
            )
        ).all()
    )


async def member_count(session: AsyncSession, org_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.org_id == org_id, Membership.status == "active")
    )
    return int(count or 0)


async def update_profile(
    session: AsyncSession,
    member: Membership,
    *,
    pseudo: str | None = None,
    avatar: dict[str, Any] | None = None,
) -> Membership:
    if pseudo is not None and pseudo != member.pseudo:
        if await pseudo_taken(session, member.org_id, pseudo, except_member=member.id):
            raise AppError("pseudo_taken")
        member.pseudo = pseudo
    if avatar is not None:
        member.avatar = checked_drawing("avatar", avatar, await unlocked_colors(session, member))
    await session.flush()
    await bus.publish(
        session,
        "member.updated",
        {"member": public_member(member)},
        topics=[f"org:{member.org_id}"],
    )
    return member


async def unlocked_colors(session: AsyncSession, member: Membership) -> set[int]:
    """Colours beyond the base palette that the member unlocked (collection, US7)."""
    return set()
