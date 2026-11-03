"""Coins (research.md J6): Monday's conversion of gold laurels, purchases, and the good news."""

import uuid
from collections.abc import Collection
from datetime import date, datetime

from sqlalchemy import func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Bet, CoinEntry, Membership, Organisation
from sibylle.domain.coins import CoinKind, gold, weekly_amount
from sibylle.domain.seasons import week_bounds, week_start
from sibylle.realtime import bus
from sibylle.services import ledger


async def in_play(
    session: AsyncSession, membership_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Each member's stakes on pronos not settled yet. A stake replaced by a new date on an
    open-ended prono no longer counts: it can only be lost, or refunded by a cancellation."""
    if not membership_ids:
        return {}
    rows = await session.execute(
        select(Bet.membership_id, func.sum(Bet.stake))
        .where(
            Bet.membership_id.in_(membership_ids),
            Bet.superseded_at.is_(None),
            Bet.outcome == "pending",
        )
        .group_by(Bet.membership_id)
    )
    return {member_id: int(total) for member_id, total in rows}


async def in_play_of(session: AsyncSession, member: Membership) -> int:
    return (await in_play(session, [member.id])).get(member.id, 0)


async def append(
    session: AsyncSession,
    membership_id: uuid.UUID,
    kind: CoinKind,
    amount: int,
    *,
    item_key: str | None = None,
) -> CoinEntry:
    """Writes one entry and moves the member's coins in the same transaction."""
    member = await ledger.lock_member(session, membership_id)
    entry = CoinEntry(
        org_id=member.org_id,
        membership_id=member.id,
        kind=kind.value,
        amount=amount,
        item_key=item_key,
    )
    session.add(entry)
    member.coins += amount
    await session.flush()
    return entry


async def grant_week(
    session: AsyncSession,
    *,
    org_id: uuid.UUID | None = None,
    arrived_before: datetime | None = None,
) -> int:
    """Turns the gold laurels of each active member into as many coins, once per week; returns
    how many members were converted. Members who arrived after Monday 00:00 wait for the next
    Monday. A member locked by a settlement is skipped, never waited for: the next run gets them.

    `org_id` keeps one newsroom, and `arrived_before` moves the arrival limit: the demo seed
    converts its brand-new members straight away.
    """
    now = clock.now()
    week = week_start(now)
    monday, _ = week_bounds(now)
    newsroom = Membership.org_id == org_id if org_id is not None else true()
    converted = select(CoinEntry.id).where(
        CoinEntry.membership_id == Membership.id, CoinEntry.week_start == week
    )
    members = (
        await session.scalars(
            select(Membership)
            .join(Organisation, Organisation.id == Membership.org_id)
            .where(
                Membership.status == "active",
                Membership.joined_at < (arrived_before or monday),
                Organisation.deleted_at.is_(None),
                newsroom,
                ~converted.exists(),
            )
            .order_by(Membership.id)
            .with_for_update(of=Membership, skip_locked=True)
            .execution_options(populate_existing=True)
        )
    ).all()
    stakes = await in_play(session, [member.id for member in members])
    done = 0
    for member in members:
        member_gold = gold(member.balance, stakes.get(member.id, 0))
        amount = weekly_amount(member_gold)
        # A conversion at 0 coins is written too, so that the member is not looked at again.
        written = await session.scalar(
            insert(CoinEntry)
            .values(
                org_id=member.org_id,
                membership_id=member.id,
                kind=CoinKind.WEEKLY.value,
                amount=amount,
                week_start=week,
                gold=member_gold,
            )
            .on_conflict_do_nothing(index_elements=["membership_id", "week_start"])
            .returning(CoinEntry.id)
        )
        if written is None:
            continue
        done += 1
        member.coins += amount
        if amount:
            await bus.publish(
                session,
                "coins.granted",
                {
                    "org_id": str(member.org_id),
                    "week_start": week.isoformat(),
                    "amount": amount,
                    "coins": member.coins,
                },
                topics=[f"me:{member.account_id}"],
            )
    await session.flush()
    return done


async def unannounced(session: AsyncSession, member: Membership) -> CoinEntry | None:
    """The latest conversion that brought coins and that the member was not told about yet."""
    query = select(CoinEntry).where(
        CoinEntry.membership_id == member.id,
        CoinEntry.kind == CoinKind.WEEKLY.value,
        CoinEntry.amount > 0,
    )
    if member.coins_seen_week is not None:
        query = query.where(CoinEntry.week_start > member.coins_seen_week)
    entry: CoinEntry | None = await session.scalar(
        query.order_by(CoinEntry.week_start.desc()).limit(1)
    )
    return entry


async def mark_seen(session: AsyncSession, member: Membership, week: date) -> None:
    """The good news of that week, and of the weeks before, will not show again."""
    if week.weekday() != 0:
        raise AppError("validation_error", {"week_start": "not_monday"})
    if week > week_start(clock.now()):
        raise AppError("validation_error", {"week_start": "in_future"})
    if member.coins_seen_week is None or member.coins_seen_week < week:
        member.coins_seen_week = week
        await session.flush()
