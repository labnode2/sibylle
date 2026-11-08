"""Closing a newsroom's season: trophies engraved with the gold laurels, back to the starting
balance.

A season closes once it is over and every bet placed in it has its result (an open-ended prono
apart). The laurels of a bet go to the season it was placed in (ledger.append), so that what is
played in the next season meanwhile stays out of the trophy and out of the reset.

A closure is one transaction that starts by writing its `season_closures` row: a second run (two
workers, a restart) stops at that row and pays nothing twice.
"""

import uuid

from sqlalchemy import ColumnElement, and_, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from sibylle import clock
from sibylle.db.models import (
    Bet,
    LedgerEntry,
    Membership,
    Organisation,
    Prono,
    Season,
    SeasonClosure,
    Trophy,
)
from sibylle.domain.leaderboard import on_podium, rank
from sibylle.domain.ledger import season_reset
from sibylle.domain.seasons import next_season, season_bounds, season_of
from sibylle.realtime import bus
from sibylle.services import ledger

# Members who keep a balance across seasons; an anonymized member has nobody to give it to.
_KEEPING = ("active", "left")


async def ensure_seasons(session: AsyncSession) -> None:
    """Adds the current and the next season to the table when they are missing."""
    key = season_of(clock.now())
    for season in (key, next_season(key)):
        starts_at, ends_at = season_bounds(season.year, season.name)
        await session.execute(
            insert(Season)
            .values(year=season.year, name=season.name, starts_at=starts_at, ends_at=ends_at)
            .on_conflict_do_nothing(index_elements=["year", "name"])
        )


async def due(
    session: AsyncSession, org_id: uuid.UUID | None = None
) -> list[tuple[uuid.UUID, int]]:
    """(newsroom, season) pairs to close, oldest first: each newsroom's oldest season over (that
    it saw end) not closed yet, once every bet placed before that season's end has its result.
    A bet on an open-ended prono does not hold it back: its stake is engraved with the gold
    laurels. A season held back holds back the newsroom's later ones. `org_id` keeps one
    newsroom only."""
    closed = exists().where(
        SeasonClosure.org_id == Organisation.id, SeasonClosure.season_id == Season.id
    )
    waiting = (
        select(Bet.id)
        .join(Membership, Membership.id == Bet.membership_id)
        .join(Prono, Prono.id == Bet.prono_id)
        .where(
            Membership.org_id == Organisation.id,
            Bet.placed_at < Season.ends_at,
            Bet.outcome == "pending",
            Bet.superseded_at.is_(None),
            Prono.open_ended.is_(False),
        )
        .correlate(Organisation, Season)
        .exists()
    )
    query = (
        select(Organisation.id, Season.id, waiting)
        .select_from(Organisation)
        .join(
            Season,
            and_(Season.ends_at <= clock.now(), Season.ends_at > Organisation.created_at),
        )
        .where(Organisation.deleted_at.is_(None), ~closed)
        .order_by(Season.starts_at, Organisation.id)
    )
    if org_id is not None:
        query = query.where(Organisation.id == org_id)
    pairs: list[tuple[uuid.UUID, int]] = []
    seen: set[uuid.UUID] = set()
    for org, season_id, held in await session.execute(query):
        if org in seen:
            continue
        seen.add(org)
        if not held:
            pairs.append((org, season_id))
    return pairs


async def _sums(
    session: AsyncSession, column: InstrumentedAttribute[int], where: ColumnElement[bool]
) -> dict[uuid.UUID, int]:
    """Each member's sum of a ledger column over the matching entries."""
    rows = await session.execute(
        select(LedgerEntry.membership_id, func.sum(column))
        .where(where)
        .group_by(LedgerEntry.membership_id)
    )
    return {member: int(total) for member, total in rows}


async def gold_laurels(
    session: AsyncSession, org_id: uuid.UUID, season: Season
) -> dict[uuid.UUID, int]:
    """Each member's gold laurels at the end of `season`: the green ones the ledger gives up to
    that season, plus the stakes still in play on bets placed before its end. A member with no
    laurels up to that season (arrived after it) is missing."""
    up_to = and_(
        LedgerEntry.org_id == org_id,
        LedgerEntry.season_id.in_(select(Season.id).where(Season.starts_at <= season.starts_at)),
    )
    green = await _sums(session, LedgerEntry.amount, up_to)
    in_play = await session.execute(
        select(Bet.membership_id, func.sum(Bet.stake))
        .join(Membership, Membership.id == Bet.membership_id)
        .where(
            Membership.org_id == org_id,
            Bet.placed_at < season.ends_at,
            Bet.outcome == "pending",
            Bet.superseded_at.is_(None),
        )
        .group_by(Bet.membership_id)
    )
    for member, stakes in in_play:
        green[member] = green.get(member, 0) + int(stakes)
    return green


async def close(session: AsyncSession, org_id: uuid.UUID, season_id: int) -> bool:
    """Closes one newsroom's season; False when it was already closed."""
    claimed = await session.scalar(
        insert(SeasonClosure)
        .values(org_id=org_id, season_id=season_id, closed_at=clock.now())
        .on_conflict_do_nothing()
        .returning(SeasonClosure.org_id)
    )
    if claimed is None:
        return False
    org = await session.get(Organisation, org_id)
    season = await session.get(Season, season_id)
    assert org is not None and season is not None
    # Locked in id order, like a settlement does, so that a prono settled at the same moment
    # cannot deadlock with the closure; then read in name order.
    locked = (
        await session.scalars(
            select(Membership.id)
            .where(Membership.org_id == org_id)
            .order_by(Membership.id)
            .with_for_update()
        )
    ).all()
    members = (
        await session.scalars(
            select(Membership)
            .where(Membership.id.in_(locked))
            .order_by(func.lower(Membership.pseudo), Membership.id)
        )
    ).all()

    # The trophy engraves the gold laurels at the end of the season: what the ledger gives up
    # to it (the bets placed in it included, whenever they were settled), plus the stakes still
    # in play on open-ended pronos.
    gold = await gold_laurels(session, org_id, season)
    in_season = and_(LedgerEntry.org_id == org_id, LedgerEntry.season_id == season_id)
    # Who played: a bet placed in the season, or a bet's laurels in it (an open-ended prono's
    # bet from an earlier season, settled in this one).
    moved = set(
        (
            await session.scalars(
                select(LedgerEntry.membership_id).where(in_season, LedgerEntry.bet_id.is_not(None))
            )
        ).all()
    )
    bettors = set(
        (
            await session.scalars(
                select(Bet.membership_id)
                .join(Membership, Membership.id == Bet.membership_id)
                .where(
                    Membership.org_id == org_id,
                    Bet.placed_at >= season.starts_at,
                    Bet.placed_at < season.ends_at,
                )
            )
        ).all()
    )
    players = [
        (m, gold.get(m.id, 0))
        for m in members
        if m.status in _KEEPING and (m.id in bettors or m.id in moved)
    ]
    for standing in rank(players):
        session.add(
            Trophy(
                membership_id=standing.key.id,
                season_id=season_id,
                score=standing.value,
                rank=standing.rank,
                podium=on_podium(standing.rank),
            )
        )

    current = await ledger.current_season_id(session)
    new_scores = await _sums(
        session,
        LedgerEntry.score_delta,
        and_(LedgerEntry.org_id == org_id, LedgerEntry.season_id == current),
    )
    for member in members:
        member.season_score = new_scores.get(member.id, 0)
    # Written before the resets: appending to the ledger reloads each member's row.
    await session.flush()
    # Everyone's gold laurels back to the starting balance, in the next season: what was played
    # there meanwhile stays, and a stake still in play counts in the gold laurels.
    following = await ledger.season_id_of(session, next_season(season_of(season.starts_at)))
    for member in members:
        if member.status not in _KEEPING or member.id not in gold:
            continue
        reset = season_reset(starting=org.starting_balance, current=gold[member.id])
        if reset.amount:
            await ledger.append(session, member.id, reset, season_id=following)

    await bus.publish(
        session,
        "season.closed",
        {"season": {"year": season.year, "name": season.name}},
        topics=[f"org:{org_id}"],
    )
    return True
