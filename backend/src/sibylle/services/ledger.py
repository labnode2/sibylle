"""Writing to the laurels ledger, keeping each member's balance and score caches in step."""

import uuid
from dataclasses import dataclass

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Bet, LedgerEntry, Membership, Prono, Season, SeasonClosure
from sibylle.domain.ledger import Effect, LedgerKind, reversal
from sibylle.domain.seasons import SeasonKey, season_bounds, season_of
from sibylle.realtime import bus


async def season_id_of(session: AsyncSession, key: SeasonKey) -> int:
    """The id of a season, adding it to the table if it is not there yet."""
    season_id = await session.scalar(
        select(Season.id).where(Season.year == key.year, Season.name == key.name)
    )
    if season_id is None:
        starts_at, ends_at = season_bounds(key.year, key.name)
        season = Season(year=key.year, name=key.name, starts_at=starts_at, ends_at=ends_at)
        session.add(season)
        await session.flush()
        season_id = season.id
    return season_id


async def current_season_id(session: AsyncSession) -> int:
    """The id of the season we are in, adding it to the table if it is not there yet."""
    return await season_id_of(session, season_of(clock.now()))


async def _bet_season_id(session: AsyncSession, org_id: uuid.UUID, bet_id: uuid.UUID) -> int | None:
    """Where a bet's laurels go: the season it was placed in, until the newsroom closes that
    season; then the oldest season the newsroom has not closed yet. A season closes only once
    its bets are settled (seasons.due), so only an open-ended prono's bet comes here late."""
    placed_at = select(Bet.placed_at).where(Bet.id == bet_id).scalar_subquery()
    closed = exists().where(SeasonClosure.org_id == org_id, SeasonClosure.season_id == Season.id)
    season_id: int | None = await session.scalar(
        select(Season.id)
        .where(Season.ends_at > placed_at, ~closed)
        .order_by(Season.starts_at)
        .limit(1)
    )
    return season_id


async def lock_member(session: AsyncSession, membership_id: uuid.UUID) -> Membership:
    """Locks a member's row for the rest of the transaction and reloads it."""
    member = await session.scalar(
        select(Membership)
        .where(Membership.id == membership_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if member is None:
        raise LookupError(f"no membership {membership_id}")
    return member


async def append(
    session: AsyncSession,
    membership_id: uuid.UUID,
    effect: Effect,
    *,
    prono_id: uuid.UUID | None = None,
    bet_id: uuid.UUID | None = None,
    settlement_id: uuid.UUID | None = None,
    reverses_entry_id: int | None = None,
    reason: str | None = None,
    actor_membership_id: uuid.UUID | None = None,
    season_id: int | None = None,
) -> LedgerEntry:
    """Writes one entry and moves the member's caches in the same transaction. The entry goes
    to `season_id` when given, to its bet's season for a bet, otherwise to the current season."""
    member = await lock_member(session, membership_id)
    current = await current_season_id(session)
    if season_id is None and bet_id is not None and effect.kind is not LedgerKind.STAKE:
        season_id = await _bet_season_id(session, member.org_id, bet_id)
    if season_id is None:
        season_id = current
    entry = LedgerEntry(
        org_id=member.org_id,
        membership_id=member.id,
        season_id=season_id,
        kind=effect.kind.value,
        amount=effect.amount,
        score_delta=effect.score_delta,
        prono_id=prono_id,
        bet_id=bet_id,
        settlement_id=settlement_id,
        reverses_entry_id=reverses_entry_id,
        reason=reason,
        actor_membership_id=actor_membership_id,
    )
    session.add(entry)
    member.balance += effect.amount
    if season_id == current:
        member.season_score += effect.score_delta
    await session.flush()
    await bus.publish(
        session,
        "balance.changed",
        {
            "org_id": str(member.org_id),
            "balance": member.balance,
            "season_score": member.season_score,
        },
        topics=[f"me:{member.account_id}"],
    )
    return entry


async def reverse(
    session: AsyncSession,
    entry: LedgerEntry,
    *,
    settlement_id: uuid.UUID | None = None,
    actor_membership_id: uuid.UUID | None = None,
) -> LedgerEntry:
    """Cancels an entry by appending its exact opposite."""
    original = Effect(LedgerKind(entry.kind), entry.amount, entry.score_delta)
    return await append(
        session,
        entry.membership_id,
        reversal(original),
        prono_id=entry.prono_id,
        bet_id=entry.bet_id,
        settlement_id=settlement_id,
        reverses_entry_id=entry.id,
        actor_membership_id=actor_membership_id,
    )


@dataclass(frozen=True)
class CacheMismatch:
    membership_id: uuid.UUID
    balance: int
    ledger_balance: int
    season_score: int
    ledger_season_score: int


async def check_caches(session: AsyncSession, org_id: uuid.UUID) -> list[CacheMismatch]:
    """Members whose cached balance or season score differs from the ledger's sums."""
    season_id = await current_season_id(session)
    season_score = func.coalesce(
        func.sum(LedgerEntry.score_delta).filter(LedgerEntry.season_id == season_id), 0
    )
    rows = await session.execute(
        select(
            Membership.id,
            Membership.balance,
            Membership.season_score,
            func.coalesce(func.sum(LedgerEntry.amount), 0),
            season_score,
        )
        .outerjoin(LedgerEntry, LedgerEntry.membership_id == Membership.id)
        .where(Membership.org_id == org_id)
        .group_by(Membership.id)
    )
    return [
        CacheMismatch(member_id, balance, ledger_balance, score, ledger_score)
        for member_id, balance, score, ledger_balance, ledger_score in rows
        if balance != ledger_balance or score != ledger_score
    ]


async def statement(
    session: AsyncSession, membership_id: uuid.UUID, *, cursor: str | None, limit: int
) -> tuple[list[tuple[LedgerEntry, str | None]], str | None]:
    """A member's entries, newest first, each with its prono's question; then the next cursor."""
    query = (
        select(LedgerEntry, Prono.question)
        .outerjoin(Prono, Prono.id == LedgerEntry.prono_id)
        .where(LedgerEntry.membership_id == membership_id)
    )
    if cursor:
        if not cursor.isdigit():
            raise AppError("validation_error", {"cursor": "invalid"})
        query = query.where(LedgerEntry.id < int(cursor))
    rows = (await session.execute(query.order_by(LedgerEntry.id.desc()).limit(limit + 1))).all()
    page: list[tuple[LedgerEntry, str | None]] = [
        (entry, question) for entry, question in rows[:limit]
    ]
    return page, str(page[-1][0].id) if len(rows) > limit else None
