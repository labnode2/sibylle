"""Closing a newsroom's season: trophies, back to the starting balance, a fresh season score.

A closure is one transaction that starts by writing its `season_closures` row: a second run (two
workers, a restart) stops at that row and pays nothing twice.
"""

import uuid

from sqlalchemy import ColumnElement, and_, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sybille import clock
from sybille.db.models import (
    Bet,
    LedgerEntry,
    Membership,
    Organisation,
    Season,
    SeasonClosure,
    Trophy,
)
from sybille.domain.leaderboard import on_podium, rank
from sybille.domain.ledger import season_reset
from sybille.domain.seasons import next_season, season_bounds, season_of
from sybille.realtime import bus
from sybille.services import ledger

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
    """(newsroom, season) pairs to close: seasons over, that the newsroom saw end, oldest first.
    `org_id` keeps one newsroom only."""
    closed = exists().where(
        SeasonClosure.org_id == Organisation.id, SeasonClosure.season_id == Season.id
    )
    query = (
        select(Organisation.id, Season.id)
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
    rows = await session.execute(query)
    return [(org_id, season_id) for org_id, season_id in rows]


async def _scores(session: AsyncSession, where: ColumnElement[bool]) -> dict[uuid.UUID, int]:
    """Each member's sum of `score_delta` over the matching ledger entries."""
    rows = await session.execute(
        select(LedgerEntry.membership_id, func.sum(LedgerEntry.score_delta))
        .where(where)
        .group_by(LedgerEntry.membership_id)
    )
    return {member: int(score) for member, score in rows}


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
    members = (
        await session.scalars(
            select(Membership)
            .where(Membership.org_id == org_id)
            .order_by(func.lower(Membership.pseudo), Membership.id)
            .with_for_update()
        )
    ).all()

    # The trophy engraves the season's score from the ledger, so that a prono settled after
    # midnight but before this closure stays in the new season.
    in_season = and_(LedgerEntry.org_id == org_id, LedgerEntry.season_id == season_id)
    scores = await _scores(session, in_season)
    # Who played: a bet placed in the season, or a score moved in it (a bet placed the season
    # before and settled in this one), so that all time adds up every season's score.
    moved = set(
        (
            await session.scalars(
                select(LedgerEntry.membership_id).where(in_season, LedgerEntry.score_delta != 0)
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
        (m, scores.get(m.id, 0))
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
    new_scores = await _scores(
        session, and_(LedgerEntry.org_id == org_id, LedgerEntry.season_id == current)
    )
    for member in members:
        member.season_score = new_scores.get(member.id, 0)
    # Written before the resets: appending to the ledger reloads each member's row.
    await session.flush()
    for member in members:
        if member.status not in _KEEPING:
            continue
        reset = season_reset(starting=org.starting_balance, current=member.balance)
        if reset.amount:
            await ledger.append(session, member.id, reset)

    await bus.publish(
        session,
        "season.closed",
        {"season": {"year": season.year, "name": season.name}},
        topics=[f"org:{org_id}"],
    )
    return True
