"""The notifications outbox: rows written with the event that causes them, sent by the worker.

Also who gets the four notifications of US8 (contracts/notifications.md), the switches of each
account and its push devices.
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import (
    Account,
    Bet,
    Membership,
    Notification,
    NotificationPref,
    Organisation,
    Prono,
    PushSubscription,
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
    return len(result.all())


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


async def still_relevant(session: AsyncSession, notification: Notification) -> bool:
    """Whether the notification still has an object when it leaves (otherwise `skipped`)."""
    payload = notification.payload
    member = await session.get(Membership, uuid.UUID(payload["member_id"]))
    if member is None or member.status != "active":
        return False
    org = await session.get(Organisation, member.org_id)
    prono = await session.get(Prono, uuid.UUID(payload["prono_id"]))
    if org is None or org.deleted_at is not None or prono is None:
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


# Switches


async def prefs(session: AsyncSession, account_id: uuid.UUID) -> list[tuple[str, str, bool]]:
    """The eight switches, in the contract's order; the ones never touched are on."""
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
