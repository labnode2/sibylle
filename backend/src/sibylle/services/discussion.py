"""The discussion under each prono (US14, research.md J9): messages read by pages, written,
liked and deleted. The screens follow it through the prono's topic: the events carry ids, and
each screen reads the discussion again, since `liked` and `can_delete` depend on the reader."""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Membership, Message, MessageLike, Prono
from sibylle.domain.permissions import Action, can
from sibylle.realtime import bus
from sibylle.services.orgs import public_member
from sibylle.services.pronos import HIDDEN_STATES, get_prono

PAGE = 20
PAGE_MAX = 50
BODY_MAX = 500


async def _published(session: AsyncSession, member: Membership, prono_id: uuid.UUID) -> Prono:
    """The prono, if the member sees it; its discussion opens with its publication."""
    prono = await get_prono(session, member, prono_id)
    if prono.state in HIDDEN_STATES:
        raise AppError("invalid_state")
    return prono


async def _message(
    session: AsyncSession, prono: Prono, message_id: uuid.UUID, *, lock: bool = False
) -> Message:
    query = select(Message).where(Message.id == message_id, Message.prono_id == prono.id)
    if lock:
        query = query.with_for_update()
    message = await session.scalar(query)
    if message is None:
        raise AppError("not_found")
    return message


async def message_count(session: AsyncSession, prono_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count()).select_from(Message).where(Message.prono_id == prono_id)
    )
    return int(count or 0)


def _may_delete(member: Membership, message: Message) -> bool:
    return message.membership_id == member.id or can(member.role, Action.MODERATE_MESSAGES)


async def _views(
    session: AsyncSession, member: Membership, rows: Sequence[tuple[Message, Membership]]
) -> list[dict[str, Any]]:
    likers: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    for message_id, liker_id, pseudo in await session.execute(
        select(MessageLike.message_id, Membership.id, Membership.pseudo)
        .join(Membership, Membership.id == MessageLike.membership_id)
        .where(MessageLike.message_id.in_([message.id for message, _ in rows]))
        .order_by(MessageLike.created_at, MessageLike.membership_id)
    ):
        likers[message_id].append((liker_id, pseudo))
    return [
        {
            "id": message.id,
            "author": public_member(author),
            "body": message.body,
            "created_at": message.created_at,
            "likes": len(likers[message.id]),
            "liked": any(liker_id == member.id for liker_id, _ in likers[message.id]),
            "likers": [pseudo for _, pseudo in likers[message.id]],
            "can_delete": _may_delete(member, message),
        }
        for message, author in rows
    ]


async def page(
    session: AsyncSession,
    member: Membership,
    prono_id: uuid.UUID,
    *,
    before: uuid.UUID | None = None,
    limit: int = PAGE,
) -> tuple[list[dict[str, Any]], bool]:
    """The `limit` messages written before `before` (or the latest ones), oldest first, and
    whether older ones are left."""
    prono = await _published(session, member, prono_id)
    query = (
        select(Message, Membership)
        .join(Membership, Membership.id == Message.membership_id)
        .where(Message.prono_id == prono.id)
    )
    if before is not None:
        query = query.where(Message.id < before)
    rows = (await session.execute(query.order_by(Message.id.desc()).limit(limit + 1))).all()
    newest_first = [(message, author) for message, author in rows[:limit]]
    return await _views(session, member, newest_first[::-1]), len(rows) > limit


async def _announce(session: AsyncSession, prono: Prono, event: str, message_id: uuid.UUID) -> None:
    await bus.publish(
        session,
        event,
        {
            "prono_id": str(prono.id),
            "message_id": str(message_id),
            "message_count": await message_count(session, prono.id),
        },
        topics=[f"prono:{prono.id}"],
    )


async def write(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, body: str
) -> dict[str, Any]:
    if not can(member.role, Action.DISCUSS):
        raise AppError("forbidden")
    prono = await _published(session, member, prono_id)
    text = body.strip()
    if not text:
        raise AppError("validation_error", {"body": "empty"})
    if len(text) > BODY_MAX:
        raise AppError("validation_error", {"body": "too_long"})
    message = Message(prono_id=prono.id, membership_id=member.id, body=text)
    session.add(message)
    await session.flush()
    await _announce(session, prono, "message.posted", message.id)
    [view] = await _views(session, member, [(message, member)])
    return view


async def remove(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, message_id: uuid.UUID
) -> None:
    """Its author deletes a message, or the editor removes it; its likes go with it."""
    prono = await get_prono(session, member, prono_id)
    message = await _message(session, prono, message_id, lock=True)
    if not _may_delete(member, message):
        raise AppError("forbidden")
    await session.execute(delete(Message).where(Message.id == message.id))
    await _announce(session, prono, "message.deleted", message.id)


async def like(
    session: AsyncSession,
    member: Membership,
    prono_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    on: bool,
) -> None:
    """Likes (`on`) a message or takes the like back; doing it twice changes nothing."""
    prono = await get_prono(session, member, prono_id)
    # Held until the end: a message deleted meanwhile waits for the like, and takes it along.
    message = await session.scalar(
        select(Message)
        .where(Message.id == message_id, Message.prono_id == prono.id)
        .with_for_update(key_share=True)
    )
    if message is None:
        raise AppError("not_found")
    if on:
        await session.execute(
            insert(MessageLike)
            .values(message_id=message.id, membership_id=member.id, created_at=clock.now())
            .on_conflict_do_nothing()
        )
    else:
        await session.execute(
            delete(MessageLike).where(
                MessageLike.message_id == message.id, MessageLike.membership_id == member.id
            )
        )
    likes = await session.scalar(
        select(func.count()).select_from(MessageLike).where(MessageLike.message_id == message.id)
    )
    await bus.publish(
        session,
        "message.liked",
        {"prono_id": str(prono.id), "message_id": str(message.id), "likes": int(likes or 0)},
        topics=[f"prono:{prono.id}"],
    )
