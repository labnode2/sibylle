"""The notifications outbox: rows written with the event that causes them, sent by the worker.

Also who gets the notifications of US8 and the reports' one (contracts/notifications.md), the
switches of each account and its push devices.
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Text, and_, cast, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import (
    Account,
    Bet,
    Membership,
    Message,
    Notification,
    NotificationPref,
    Organisation,
    Prono,
    PushSubscription,
    Report,
    Settlement,
)
from sibylle.domain.lifecycle import State
from sibylle.domain.notifications import (
    CLOSING_SOON,
    Channel,
    NotificationType,
    reminder_base,
    reminder_step,
)
from sibylle.domain.permissions import Action, can
from sibylle.realtime import bus


async def enqueue(
    session: AsyncSession,
    *,
    type: str,
    payload: dict[str, Any],
    dedupe_key: str,
    account_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    scheduled_at: datetime | None = None,
) -> bool:
    """Queues a notification; a second one with the same `dedupe_key` is ignored.

    Returns whether a row was added.
    """
    added = await enqueue_many(
        session,
        [
            {
                "account_id": account_id,
                "org_id": org_id,
                "type": type,
                "payload": payload,
                "dedupe_key": dedupe_key,
                "next_attempt_at": scheduled_at or clock.now(),
            }
        ],
    )
    return added == 1


async def enqueue_many(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> int:
    """Queues several notifications at once; returns how many were new."""
    if not rows:
        return 0
    now = clock.now()
    result = await session.execute(
        insert(Notification)
        .values([{"next_attempt_at": now, **row} for row in rows])
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(Notification.id)
    )
    added = result.all()
    # The bubbles of whoever is on the app move at once (the event leaves with the commit).
    for account_id, org_id in {
        (row["account_id"], row.get("org_id")) for row in rows if row.get("account_id")
    }:
        if org_id is not None:
            await _changed(session, account_id, org_id, "notification.created")
    return len(added)


async def _changed(
    session: AsyncSession, account_id: uuid.UUID, org_id: uuid.UUID, event: str
) -> None:
    await bus.publish(
        session,
        event,
        {"org_id": str(org_id)},
        topics=[f"me:{account_id}"],
    )


# Who gets what


def _about(org: Organisation, prono: Prono, member_id: uuid.UUID) -> dict[str, Any]:
    return {
        "org_id": str(org.id),
        "org_title": org.title,
        "prono_id": str(prono.id),
        "question": prono.question,
        "member_id": str(member_id),
    }


async def _active_members(
    session: AsyncSession, org_id: uuid.UUID, member_ids: Iterable[uuid.UUID] | None = None
) -> list[Membership]:
    """The newsroom's active members whose account still exists (all, or among `member_ids`)."""
    query = (
        select(Membership)
        .join(Account, Account.id == Membership.account_id)
        .where(
            Membership.org_id == org_id,
            Membership.status == "active",
            Account.deleted_at.is_(None),
        )
        .order_by(Membership.joined_at)
    )
    if member_ids is not None:
        query = query.where(Membership.id.in_(list(member_ids)))
    return list((await session.scalars(query)).all())


def _row(
    type: NotificationType, member: Membership, key: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "type": type.value,
        "account_id": member.account_id,
        "org_id": member.org_id,
        "payload": payload,
        "dedupe_key": key,
    }


async def prono_opened(session: AsyncSession, prono: Prono, actor: Membership | None) -> int:
    """« Nouveau prono » for every active member, except its author and whoever opened it."""
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    skip = {prono.created_by, actor.id if actor else None}
    members = [m for m in await _active_members(session, org.id) if m.id not in skip]
    return await enqueue_many(
        session,
        [
            _row(
                NotificationType.NEW_PRONO,
                member,
                f"new_prono:{prono.id}:{member.account_id}",
                _about(org, prono, member.id),
            )
            for member in members
        ],
    )


async def prono_settled(
    session: AsyncSession,
    prono: Prono,
    settlement: Settlement,
    bets: Sequence[Bet],
    result: str | None,
) -> int:
    """The special edition, for each member who bet: what they won, or their stake back."""
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    active = {bet.membership_id: bet for bet in bets if bet.superseded_at is None}
    members = await _active_members(session, org.id, active)
    return await enqueue_many(
        session,
        [
            _row(
                NotificationType.RESULT,
                member,
                f"result:{prono.id}:{settlement.seq}:{member.account_id}",
                {
                    **_about(org, prono, member.id),
                    "kind": settlement.kind,
                    "seq": settlement.seq,
                    "result": result,
                    "outcome": active[member.id].outcome,
                    "payout": active[member.id].payout,
                },
            )
            for member in members
        ],
    )


async def _bettors(session: AsyncSession, prono_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        (
            await session.scalars(
                select(Bet.membership_id).where(
                    Bet.prono_id == prono_id, Bet.superseded_at.is_(None)
                )
            )
        ).all()
    )


async def queue_closing_soon(session: AsyncSession) -> int:
    """« Ferme dans 2 h » for the members who have not bet; never for an open-ended prono."""
    now = clock.now()
    pronos = (
        await session.scalars(
            select(Prono).where(
                Prono.state == State.OPEN.value,
                Prono.closes_at > now,
                Prono.closes_at <= now + CLOSING_SOON,
            )
        )
    ).all()
    added = 0
    for prono in pronos:
        org = await session.get(Organisation, prono.org_id)
        assert org is not None
        bettors = await _bettors(session, prono.id)
        added += await enqueue_many(
            session,
            [
                _row(
                    NotificationType.CLOSING_SOON,
                    member,
                    f"closing_soon:{prono.id}:{member.account_id}",
                    _about(org, prono, member.id),
                )
                for member in await _active_members(session, org.id)
                if member.id not in bettors
            ],
        )
    return added


def _awaiting_designation() -> Any:
    return or_(
        Prono.state == State.CLOSED.value,
        (Prono.state == State.OPEN.value)
        & Prono.open_ended
        & Prono.result_expected_at.is_not(None),
    )


async def queue_designation_reminders(session: AsyncSession) -> int:
    """Reminds the journalist in charge of each result still to designate (research.md J5)."""
    now = clock.now()
    pronos = (await session.scalars(select(Prono).where(_awaiting_designation()))).all()
    added = 0
    for prono in pronos:
        base = reminder_base(closes_at=prono.closes_at, result_expected_at=prono.result_expected_at)
        step = reminder_step(base, now) if base is not None else None
        if step is None:
            continue
        # The journalist who published it, or the one who validated the reader's proposal.
        in_charge = prono.validated_by or prono.created_by
        found = await _active_members(session, prono.org_id, [in_charge])
        if not found or not can(found[0].role, Action.DESIGNATE_RESULT):
            continue
        member = found[0]
        org = await session.get(Organisation, prono.org_id)
        assert org is not None
        added += await enqueue_many(
            session,
            [
                _row(
                    NotificationType.DESIGNATION_REMINDER,
                    member,
                    f"designation:{prono.id}:{prono.relaunch_count}-{step}",
                    {**_about(org, prono, member.id), "relaunch": prono.relaunch_count},
                )
            ],
        )
    return added


async def report_created(session: AsyncSession, report: Report, prono: Prono) -> int:
    """« Nouveau signalement » for whoever may handle it, never its author nor the member it is
    about (the prono's author)."""
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    skip = {report.reporter_membership_id, prono.created_by}
    handlers = [
        member
        for member in await _active_members(session, org.id)
        if member.id not in skip and can(member.role, Action.HANDLE_REPORTS)
    ]
    return await enqueue_many(
        session,
        [
            _row(
                NotificationType.REPORT,
                member,
                f"report:{report.id}:{member.account_id}",
                {**_about(org, prono, member.id), "report_id": str(report.id), "kind": report.kind},
            )
            for member in handlers
        ],
    )


_DISCUSSION_TYPES = (NotificationType.MENTION.value, NotificationType.DISCUSSION.value)


async def message_posted(
    session: AsyncSession, prono: Prono, message: Message, author: Membership
) -> int:
    """A message in a prono's discussion: « tagged » for the members it tags, « discussion » for
    the others who wrote or were tagged there before. Never for its author, and a member with
    one of these still unread for this prono gets no second one."""
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    # Two messages written together would each see the other's notification as missing.
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"discussion:{prono.id}")))
    )
    involved: set[uuid.UUID] = set()
    for writer, tagged in await session.execute(
        select(Message.membership_id, Message.mentions).where(Message.prono_id == prono.id)
    ):
        involved.add(writer)
        involved.update(tagged)
    involved.discard(author.id)
    members = await _active_members(session, org.id, involved)
    waiting = set(
        (
            await session.scalars(
                select(Notification.account_id).where(
                    Notification.org_id == org.id,
                    Notification.type.in_(_DISCUSSION_TYPES),
                    Notification.payload["prono_id"].as_string() == str(prono.id),
                    Notification.read_at.is_(None),
                    Notification.state != "skipped",
                )
            )
        ).all()
    )
    rows = []
    for member in members:
        if member.account_id in waiting:
            continue
        type = (
            NotificationType.MENTION
            if member.id in message.mentions
            else NotificationType.DISCUSSION
        )
        rows.append(
            _row(
                type,
                member,
                f"{type.value}:{message.id}:{member.account_id}",
                {
                    **_about(org, prono, member.id),
                    "message_id": str(message.id),
                    "author": author.pseudo,
                },
            )
        )
    return await enqueue_many(session, rows)


async def still_relevant(session: AsyncSession, notification: Notification) -> bool:
    """Whether the notification still has an object when it leaves (otherwise `skipped`)."""
    payload = notification.payload
    member = await session.get(Membership, uuid.UUID(payload["member_id"]))
    if member is None or member.status != "active":
        return False
    org = await session.get(Organisation, member.org_id)
    prono = await session.get(Prono, uuid.UUID(payload["prono_id"]))
    # A deleted prono has nothing left to show: its page answers 404.
    if org is None or org.deleted_at is not None or prono is None or prono.deleted_at is not None:
        return False
    match NotificationType(notification.type):
        case NotificationType.NEW_PRONO:
            return prono.state == State.OPEN.value
        case NotificationType.CLOSING_SOON:
            return (
                prono.state == State.OPEN.value
                and prono.closes_at is not None
                and prono.closes_at > clock.now()
                and member.id not in await _bettors(session, prono.id)
            )
        case NotificationType.RESULT:
            return True
        case NotificationType.DESIGNATION_REMINDER:
            awaiting = await session.scalar(
                select(Prono.id).where(Prono.id == prono.id, _awaiting_designation())
            )
            return (
                awaiting is not None
                and prono.relaunch_count == payload["relaunch"]
                and can(member.role, Action.DESIGNATE_RESULT)
            )
        case NotificationType.REPORT:
            # Already handled by someone else, or no longer theirs to handle: nothing to tell.
            report = await session.get(Report, uuid.UUID(payload["report_id"]))
            return (
                report is not None
                and report.state == "open"
                and can(member.role, Action.HANDLE_REPORTS)
            )
        case NotificationType.MENTION | NotificationType.DISCUSSION:
            # The message may be gone, and the prono no longer open to discussion.
            return (
                prono.state not in (State.PROPOSED.value, State.REJECTED.value)
                and await session.get(Message, uuid.UUID(payload["message_id"])) is not None
            )


# The member's notifications, in a newsroom: the list, and the bubbles of the menus


def _mine(account_id: uuid.UUID, *org_ids: uuid.UUID) -> list[Any]:
    """The newsroom's notifications of this account (not the e-mails to an address without an
    account), whatever became of their push and e-mail: `skipped` also says that no channel could
    carry one, and the app still shows it to a member who switched both off."""
    return [
        Notification.account_id == account_id,
        Notification.org_id.in_(org_ids),
        Notification.type.in_([type.value for type in NotificationType]),
    ]


def _listed(account_id: uuid.UUID, org_id: uuid.UUID) -> list[Any]:
    """The list: not those that were skipped."""
    return [*_mine(account_id, org_id), Notification.state != "skipped"]


def _waiting() -> Any:
    """What a bubble still leads to, the notification's prono joined: a new prono and its last
    two hours while it is open, a reminder while the result waits, a result, a tag or a message
    until read. Never a proposal, which not everyone may open, nor a deleted prono, which nobody
    can open any more. The reports are left out: their own count, the open reports beside « La
    rédaction », leads to them. Whether it was sent does not matter (see `_mine`)."""
    while_open = (NotificationType.NEW_PRONO.value, NotificationType.CLOSING_SOON.value)
    until_read = (NotificationType.RESULT.value, *_DISCUSSION_TYPES)
    return and_(
        Prono.state.notin_((State.PROPOSED.value, State.REJECTED.value)),
        Prono.deleted_at.is_(None),
        or_(
            Notification.type.in_(while_open) & (Prono.state == State.OPEN.value),
            (Notification.type == NotificationType.DESIGNATION_REMINDER.value)
            & _awaiting_designation(),
            Notification.type.in_(until_read),
        ),
    )


def _about_prono() -> Any:
    return cast(Prono.id, Text) == Notification.payload["prono_id"].as_string()


def _bubbling(account_id: uuid.UUID, *org_ids: uuid.UUID) -> list[Any]:
    """What every bubble counts, the notification's prono joined: the account's unread
    notifications in these newsrooms that still lead to their prono (`_waiting`). The bubbles
    of a prono, of the list's filters, of « Pronos » and of the newsroom itself add up the same
    rows, so that each one leads down to the prono that clears it."""
    return [
        *_mine(account_id, *org_ids),
        Notification.read_at.is_(None),
        Prono.org_id == Notification.org_id,
        _waiting(),
    ]


async def unread_pronos(
    session: AsyncSession, account_id: uuid.UUID, org_id: uuid.UUID
) -> list[tuple[uuid.UUID, str, uuid.UUID, int]]:
    """The bubbles: per prono, its state and section (the list's filters) and how many unread
    notifications still lead to it, the most recently notified first."""
    rows = await session.execute(
        select(Prono.id, Prono.state, Prono.section_id, func.count())
        .select_from(Notification)
        .join(Prono, _about_prono())
        .where(*_bubbling(account_id, org_id))
        .group_by(Prono.id, Prono.state, Prono.section_id)
        .order_by(func.max(Notification.created_at).desc(), Prono.id)
    )
    return [(prono_id, state, section_id, count) for prono_id, state, section_id, count in rows]


async def unread_by_newsroom(
    session: AsyncSession, account_id: uuid.UUID, org_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Per newsroom, the bubble beside « Pronos »: what `unread_pronos` adds up there. A
    newsroom with none is left out."""
    if not org_ids:
        return {}
    rows = await session.execute(
        select(Notification.org_id, func.count())
        .select_from(Notification)
        .join(Prono, _about_prono())
        .where(*_bubbling(account_id, *org_ids))
        .group_by(Notification.org_id)
    )
    return {org_id: count for org_id, count in rows.all() if org_id is not None}


# Topics per event, well under PostgreSQL's limit on a payload (`bus.MAX_PAYLOAD`).
_TOPICS_PER_EVENT = 50


async def prono_state_changed(session: AsyncSession, prono: Prono) -> None:
    """A prono changed state, or was deleted: the bubbles of the members with unread notifications
    about it may change (a new prono stops counting once closed, a reminder once the result is
    designated, all of them once it is deleted). Their screens reload them, the newsroom's bubble
    in their lists of newsrooms too: those screens do not follow the newsroom's own events."""
    accounts = (
        await session.scalars(
            select(Notification.account_id)
            .distinct()
            .where(
                Notification.org_id == prono.org_id,
                Notification.account_id.is_not(None),
                Notification.read_at.is_(None),
                Notification.payload["prono_id"].as_string() == str(prono.id),
            )
        )
    ).all()
    topics = sorted(f"me:{account_id}" for account_id in accounts)
    for start in range(0, len(topics), _TOPICS_PER_EVENT):
        await bus.publish(
            session,
            "notification.changed",
            {"org_id": str(prono.org_id)},
            topics=topics[start : start + _TOPICS_PER_EVENT],
        )


async def listing(
    session: AsyncSession, account_id: uuid.UUID, org_id: uuid.UUID, limit: int = 50
) -> list[Notification]:
    """The most recent first."""
    return list(
        (
            await session.scalars(
                select(Notification)
                .where(*_listed(account_id, org_id))
                .order_by(Notification.created_at.desc(), Notification.id)
                .limit(limit)
            )
        ).all()
    )


async def unread_count(session: AsyncSession, account_id: uuid.UUID, org_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(*_listed(account_id, org_id), Notification.read_at.is_(None))
        )
    ) or 0


async def mark_read(
    session: AsyncSession,
    account_id: uuid.UUID,
    org_id: uuid.UUID,
    notification_id: uuid.UUID | None = None,
    *,
    prono_id: uuid.UUID | None = None,
) -> None:
    """One notification (404 when it is not this member's in this newsroom), those about a
    prono (the member opened it), or all of them. Skipped ones too: every bubble must go once its
    prono is opened."""
    query = update(Notification).where(*_mine(account_id, org_id), Notification.read_at.is_(None))
    if notification_id is not None:
        found = await session.scalar(
            select(Notification.id).where(
                *_mine(account_id, org_id), Notification.id == notification_id
            )
        )
        if found is None:
            raise AppError("not_found")
        query = query.where(Notification.id == notification_id)
    if prono_id is not None:
        query = query.where(Notification.payload["prono_id"].as_string() == str(prono_id))
    result = await session.execute(
        query.values(read_at=clock.now()).execution_options(synchronize_session=False)
    )
    if result.rowcount:  # type: ignore[attr-defined]
        await _changed(session, account_id, org_id, "notification.read")


# Switches


async def prefs(session: AsyncSession, account_id: uuid.UUID) -> list[tuple[str, str, bool]]:
    """The switches (two per type), in the contract's order; the ones never touched are on."""
    stored = {
        (pref.type, pref.channel): pref.enabled
        for pref in await session.scalars(
            select(NotificationPref).where(NotificationPref.account_id == account_id)
        )
    }
    return [
        (type.value, channel.value, stored.get((type.value, channel.value), True))
        for type in NotificationType
        for channel in Channel
    ]


async def set_prefs(
    session: AsyncSession, account_id: uuid.UUID, changes: Iterable[tuple[str, str, bool]]
) -> None:
    for type, channel, enabled in changes:
        await session.execute(
            insert(NotificationPref)
            .values(account_id=account_id, type=type, channel=channel, enabled=enabled)
            .on_conflict_do_update(
                index_elements=["account_id", "type", "channel"], set_={"enabled": enabled}
            )
        )


async def enabled_channels(session: AsyncSession, account_id: uuid.UUID, type: str) -> set[Channel]:
    return {
        Channel(channel)
        for t, channel, enabled in await prefs(session, account_id)
        if t == type and enabled
    }


# Push devices


async def subscribe(
    session: AsyncSession,
    account: Account,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None,
) -> uuid.UUID:
    """Records a device; a device already known now belongs to whoever signed in on it."""
    values = {"account_id": account.id, "p256dh": p256dh, "auth": auth, "user_agent": user_agent}
    subscription_id: uuid.UUID | None = await session.scalar(
        insert(PushSubscription)
        .values(endpoint=endpoint, created_at=clock.now(), **values)
        .on_conflict_do_update(index_elements=["endpoint"], set_=values)
        .returning(PushSubscription.id)
    )
    assert subscription_id is not None
    return subscription_id


async def unsubscribe(session: AsyncSession, account: Account, subscription_id: uuid.UUID) -> None:
    result = await session.execute(
        delete(PushSubscription)
        .where(PushSubscription.id == subscription_id, PushSubscription.account_id == account.id)
        .returning(PushSubscription.id)
    )
    if result.scalar_one_or_none() is None:
        raise AppError("not_found")


async def devices(session: AsyncSession, account_id: uuid.UUID) -> list[PushSubscription]:
    return list(
        (
            await session.scalars(
                select(PushSubscription)
                .where(PushSubscription.account_id == account_id)
                .order_by(PushSubscription.created_at, PushSubscription.id)
            )
        ).all()
    )
