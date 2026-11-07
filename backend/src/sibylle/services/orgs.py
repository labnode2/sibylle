"""Newsrooms and their members."""

import secrets
import unicodedata
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Account, LedgerEntry, Membership, Organisation, Prono, Section
from sibylle.domain.content import BACKGROUND_KEYS, DEFAULT_CHARTER, DEFAULT_LOGO
from sibylle.domain.ledger import adjustment, starting_balance
from sibylle.domain.pixels import PixelImageError, validate_pixel_image
from sibylle.realtime import bus
from sibylle.services import collection, ledger

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
        "frame": member.frame,
        "animation": member.animation,
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
        logo=checked_drawing("logo", logo) if logo else dict(DEFAULT_LOGO),
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


# Tells "leave the frame (or the animation) as it is" from "remove it" (None).
KEEP: Any = object()


async def update_profile(
    session: AsyncSession,
    member: Membership,
    *,
    pseudo: str | None = None,
    avatar: dict[str, Any] | None = None,
    frame_item_id: uuid.UUID | None = KEEP,
    animation_item_id: uuid.UUID | None = KEEP,
    showcase: list[tuple[str, uuid.UUID]] | None = None,
    card_public: bool | None = None,
) -> Membership:
    if pseudo is not None and pseudo != member.pseudo:
        if await pseudo_taken(session, member.org_id, pseudo, except_member=member.id):
            raise AppError("pseudo_taken")
        member.pseudo = pseudo
    if avatar is not None:
        member.avatar = checked_drawing("avatar", avatar, await unlocked_colors(session, member))
    if frame_item_id is not KEEP:
        member.avatar_frame = (
            await collection.owned_wearable(session, member, frame_item_id, "frame")
            if frame_item_id
            else None
        )
    if animation_item_id is not KEEP:
        member.avatar_animation = (
            await collection.owned_wearable(session, member, animation_item_id, "animation")
            if animation_item_id
            else None
        )
    if showcase is not None:
        member.showcase = await collection.checked_showcase(session, member, showcase)
    if card_public is not None:
        member.card_public = card_public
        if card_public and member.card_token is None:
            member.card_token = secrets.token_urlsafe(12)
    await session.flush()
    await bus.publish(
        session,
        "member.updated",
        {"member": public_member(member)},
        topics=[f"org:{member.org_id}"],
    )
    return member


async def unlocked_colors(session: AsyncSession, member: Membership) -> set[int]:
    """Colours beyond the base palette that the member unlocked in the collection."""
    return await collection.unlocked_colors(session, member)


# The editor's settings (US6)

_SETTINGS = (
    "title",
    "starting_balance",
    "max_base_gain",
    "early_bird_pct",
    "early_bird_count",
    "editor_note",
    "charter",
)


async def update_settings(
    session: AsyncSession, org: Organisation, changes: dict[str, Any]
) -> Organisation:
    """The card and the laurels. A new starting balance applies to newcomers and to the next
    season; a new ceiling, to the next pronos."""
    if "background_key" in changes:
        if changes["background_key"] not in BACKGROUND_KEYS:
            raise AppError("validation_error", {"background_key": "unknown"})
        org.background_key = changes["background_key"]
    if "logo" in changes:
        # No logo at all would leave an initial: taking it off brings the default one back.
        org.logo = (
            checked_drawing("logo", changes["logo"]) if changes["logo"] else dict(DEFAULT_LOGO)
        )
    for name in _SETTINGS:
        if name in changes:
            setattr(org, name, changes[name])
    if "editor_note" in changes:
        org.editor_note = (org.editor_note or "").strip() or None
    await session.flush()
    return org


async def renew_access_code(session: AsyncSession, org: Organisation) -> str:
    """A new code; the old one stops working at once."""
    org.access_code = await new_access_code(session, org.title)
    await session.flush()
    return org.access_code


async def disable_access_code(session: AsyncSession, org: Organisation) -> None:
    org.access_code = None
    await session.flush()


async def _active_member(
    session: AsyncSession, org_id: uuid.UUID, member_id: uuid.UUID, *, lock: bool = False
) -> Membership:
    query = select(Membership).where(
        Membership.id == member_id,
        Membership.org_id == org_id,
        Membership.status == "active",
    )
    member = await session.scalar(query.with_for_update() if lock else query)
    if member is None:
        raise AppError("not_found")
    return member


async def lock_editors(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Locks the newsroom before a member's role or status changes, so that two editors
    demoting each other at once cannot both pass `_keeps_an_editor`. `NO KEY UPDATE` leaves bets
    and ledger entries, whose foreign keys point at the newsroom, free to go on meanwhile."""
    await session.execute(
        select(Organisation.id).where(Organisation.id == org_id).with_for_update(key_share=True)
    )


async def _keeps_an_editor(session: AsyncSession, member: Membership) -> None:
    """Refuses to take away the newsroom's last active editor. Call `lock_editors` first."""
    if member.role != "editor":
        return
    editors = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.org_id == member.org_id,
            Membership.role == "editor",
            Membership.status == "active",
        )
    )
    if int(editors or 0) <= 1:
        raise AppError("last_editor", {"org_id": str(member.org_id)})


async def _others(session: AsyncSession, member: Membership) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.org_id == member.org_id,
            Membership.status == "active",
            Membership.id != member.id,
        )
    )
    return int(count or 0)


async def may_go(session: AsyncSession, member: Membership) -> bool:
    """Checks that the member may leave: the last editor names another first, unless nobody
    else is left. Returns whether others stay. Call `lock_editors` first."""
    others = await _others(session, member)
    if others:
        await _keeps_an_editor(session, member)
    return others > 0


async def change_role(
    session: AsyncSession, org_id: uuid.UUID, member_id: uuid.UUID, role: str
) -> Membership:
    await lock_editors(session, org_id)
    member = await _active_member(session, org_id, member_id, lock=True)
    if role != member.role:
        if role != "editor":
            await _keeps_an_editor(session, member)
        member.role = role
        await session.flush()
        await bus.publish(
            session,
            "member.updated",
            {"member": public_member(member)},
            topics=[f"org:{org_id}"],
        )
    return member


async def depart(session: AsyncSession, member: Membership, status: str = "left") -> None:
    """The member is out of the newsroom: their bets and stakes stay, their screens stop at
    once. Someone who left finds their profile again on coming back, as a reader, with their
    card private."""
    member.status = status
    member.left_at = member.left_at or clock.now()
    member.role = "reader"
    member.card_public = False
    await session.flush()
    await bus.publish(
        session,
        "member.left",
        {"member": public_member(member)},
        topics=[f"org:{member.org_id}"],
        revoke={"account_id": str(member.account_id), "org_id": str(member.org_id)},
    )


async def close(session: AsyncSession, org_id: uuid.UUID) -> None:
    """The newsroom is gone with its last member: nobody could come back to it."""
    org = await session.get(Organisation, org_id)
    assert org is not None
    org.deleted_at = clock.now()
    org.access_code = None


async def delete_org(session: AsyncSession, org: Organisation) -> None:
    """The editor deletes the newsroom. Only a mark: it disappears for every member at once,
    its pronos, laurels and members stay as they are, and `restore_org` brings it all back.
    The access code is kept for that; nobody can use it meanwhile (see invitations)."""
    if org.deleted_at is not None:
        raise AppError("not_found")
    org.deleted_at = clock.now()
    await session.flush()
    await bus.publish(session, "org.deleted", {"org_id": str(org.id)}, topics=[f"org:{org.id}"])


async def deleted_orgs(session: AsyncSession) -> list[Organisation]:
    """The newsrooms deleted by their editor or closed by their last member, latest first."""
    return list(
        (
            await session.scalars(
                select(Organisation)
                .where(Organisation.deleted_at.is_not(None))
                .order_by(Organisation.deleted_at.desc())
            )
        ).all()
    )


async def restore_org(session: AsyncSession, org_id: uuid.UUID) -> Organisation:
    """Undoes a deletion: the newsroom comes back for its active members, as it was. A newsroom
    closed by its last member comes back too, but empty, and without an access code."""
    org = await session.get(Organisation, org_id)
    if org is None or org.deleted_at is None:
        raise LookupError(f"no deleted newsroom {org_id}")
    org.deleted_at = None
    await session.flush()
    return org


async def remove_member(session: AsyncSession, org_id: uuid.UUID, member_id: uuid.UUID) -> None:
    """The editor removes a member."""
    await lock_editors(session, org_id)
    member = await _active_member(session, org_id, member_id, lock=True)
    await _keeps_an_editor(session, member)
    await depart(session, member)


async def leave(session: AsyncSession, member: Membership) -> None:
    """The member leaves on their own; the last one out closes the newsroom."""
    await lock_editors(session, member.org_id)
    member = await _active_member(session, member.org_id, member.id, lock=True)
    others_stay = await may_go(session, member)
    await depart(session, member)
    if not others_stay:
        await close(session, member.org_id)


async def adjust_laurels(
    session: AsyncSession, editor: Membership, member_id: uuid.UUID, amount: int, reason: str
) -> LedgerEntry:
    """Adds or takes laurels from a member's balance, with a reason; the score stays."""
    member = await _active_member(session, editor.org_id, member_id)
    return await ledger.append(
        session,
        member.id,
        adjustment(amount),
        reason=reason,
        actor_membership_id=editor.id,
    )


# Sections


async def active_sections(session: AsyncSession, org_id: uuid.UUID) -> list[Section]:
    return list(
        (
            await session.scalars(
                select(Section)
                .where(Section.org_id == org_id, Section.archived_at.is_(None))
                .order_by(Section.position, Section.name)
            )
        ).all()
    )


async def _check_section_name(
    session: AsyncSession, org_id: uuid.UUID, name: str, *, except_id: uuid.UUID | None = None
) -> Section | None:
    """The archived section of that name, if any; a refusal when an active one has it."""
    query = select(Section).where(
        Section.org_id == org_id, func.lower(Section.name) == name.lower()
    )
    if except_id is not None:
        query = query.where(Section.id != except_id)
    same = await session.scalar(query)
    if same is not None and same.archived_at is None:
        raise AppError("validation_error", {"name": "taken"})
    return same


def _renumber(sections: list[Section]) -> None:
    for position, section in enumerate(sections):
        section.position = position


async def create_section(session: AsyncSession, org_id: uuid.UUID, name: str) -> Section:
    """A new section at the end; an archived one of the same name comes back instead."""
    sections = await active_sections(session, org_id)
    section = await _check_section_name(session, org_id, name)
    if section is None:
        section = Section(org_id=org_id, name=name)
        session.add(section)
    section.archived_at = None
    _renumber([*sections, section])
    await session.flush()
    return section


async def update_section(
    session: AsyncSession,
    org_id: uuid.UUID,
    section_id: uuid.UUID,
    *,
    name: str | None,
    position: int | None,
) -> Section:
    sections = await active_sections(session, org_id)
    section = next((s for s in sections if s.id == section_id), None)
    if section is None:
        raise AppError("not_found")
    if name is not None and name != section.name:
        await _check_section_name(session, org_id, name, except_id=section.id)
        section.name = name
    if position is not None:
        sections.remove(section)
        sections.insert(min(position, len(sections)), section)
        _renumber(sections)
    await session.flush()
    return section


async def delete_section(session: AsyncSession, org_id: uuid.UUID, section_id: uuid.UUID) -> None:
    """Deleted when unused, archived otherwise; the last section always stays."""
    sections = await active_sections(session, org_id)
    section = next((s for s in sections if s.id == section_id), None)
    if section is None:
        raise AppError("not_found")
    if len(sections) == 1:
        raise AppError("invalid_state")
    used = await session.scalar(select(Prono.id).where(Prono.section_id == section.id).limit(1))
    if used is None:
        await session.delete(section)
    else:
        section.archived_at = clock.now()
    sections.remove(section)
    _renumber(sections)
    await session.flush()
