"""Writing to the laurels ledger, keeping each member's balance and score caches in step."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.db.models import LedgerEntry, Membership, Season
from sibylle.domain.ledger import Effect, LedgerKind, reversal
from sibylle.domain.seasons import season_bounds, season_of
from sibylle.realtime import bus


async def current_season_id(session: AsyncSession) -> int:
    """The id of the season we are in, adding it to the table if it is not there yet."""
    key = season_of(clock.now())
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
) -> LedgerEntry:
    """Writes one entry and moves the member's caches in the same transaction."""
    member = await lock_member(session, membership_id)
    entry = LedgerEntry(
        org_id=member.org_id,
        membership_id=member.id,
        season_id=await current_season_id(session),
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
