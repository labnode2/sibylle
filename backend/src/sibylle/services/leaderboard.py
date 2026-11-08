"""The rankings, computed on demand: the green laurels (plus the trophies for all time), or the
pronos won counted over the bets."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Bet, Membership, Trophy
from sibylle.domain.leaderboard import (
    Metric,
    Period,
    all_time,
    is_ranked,
    periods_of,
    rank,
    window,
)
from sibylle.domain.seasons import PARIS, season_of


@dataclass(frozen=True)
class Line:
    rank: int
    member: Membership
    value: int


@dataclass(frozen=True)
class Board:
    # "2026-11" for a month, "2026-autumn" for a season, "all_time"; the interface words it.
    period_label: str
    lines: list[Line]


async def _laurels(
    session: AsyncSession, org_id: uuid.UUID, period: Period
) -> dict[uuid.UUID, int]:
    """The green laurels, the same as in the wallet; all time adds the gold laurels engraved on
    the trophies of the closed seasons."""
    values = {
        member: balance
        for member, balance in await session.execute(
            select(Membership.id, Membership.balance).where(Membership.org_id == org_id)
        )
    }
    if period is Period.SEASON:
        return values
    engraved: dict[uuid.UUID, list[int]] = {}
    trophies = await session.execute(
        select(Trophy.membership_id, Trophy.score)
        .join(Membership, Membership.id == Trophy.membership_id)
        .where(Membership.org_id == org_id)
    )
    for member, laurels in trophies:
        engraved.setdefault(member, []).append(laurels)
    return {
        member: all_time(engraved.get(member, []), values.get(member, 0))
        for member in values.keys() | engraved.keys()
    }


async def _wins(session: AsyncSession, org_id: uuid.UUID, period: Period) -> dict[uuid.UUID, int]:
    query = (
        select(Bet.membership_id, func.count())
        .join(Membership, Membership.id == Bet.membership_id)
        .where(Membership.org_id == org_id, Bet.outcome == "won")
        .group_by(Bet.membership_id)
    )
    span = window(period, clock.now())
    if span.start is not None:
        query = query.where(Bet.settled_at >= span.start)
    if span.end is not None:
        query = query.where(Bet.settled_at < span.end)
    return {member: int(count) for member, count in await session.execute(query)}


def _label(period: Period) -> str:
    now = clock.now()
    if period is Period.MONTH:
        local = now.astimezone(PARIS)
        return f"{local.year}-{local.month:02d}"
    if period is Period.SEASON:
        key = season_of(now)
        return f"{key.year}-{key.name}"
    return "all_time"


async def values(
    session: AsyncSession, org_id: uuid.UUID, metric: Metric, period: Period
) -> dict[uuid.UUID, int]:
    """Each member's value; a member with nothing yet is missing (counts 0)."""
    if period not in periods_of(metric):
        raise AppError("validation_error", {"period": "not_for_metric"})
    if metric is Metric.LAURELS:
        return await _laurels(session, org_id, period)
    return await _wins(session, org_id, period)


async def board(session: AsyncSession, org_id: uuid.UUID, metric: Metric, period: Period) -> Board:
    """Every active member, the best first; a member with nothing yet counts 0."""
    by_member = await values(session, org_id, metric, period)
    members = (
        await session.scalars(
            select(Membership)
            .where(Membership.org_id == org_id)
            .order_by(func.lower(Membership.pseudo), Membership.id)
        )
    ).all()
    standings = rank([(m, by_member.get(m.id, 0)) for m in members if is_ranked(m.status)])
    return Board(_label(period), [Line(s.rank, s.key, s.value) for s in standings])
