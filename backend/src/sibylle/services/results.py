"""Results (research.md J1): designating, relaunching, correcting and cancelling a prono.

Each settlement is a `settlements` row; every ledger entry it writes points to it. A correction
reverses the payouts of the settlement in force before paying again, a cancellation reverses them
and gives every stake back.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import (
    Bet,
    LedgerEntry,
    Membership,
    Organisation,
    Prono,
    PronoOption,
    Settlement,
)
from sibylle.domain.betting import Kind
from sibylle.domain.closest import closest
from sibylle.domain.ledger import LedgerKind
from sibylle.domain.lifecycle import Event, InvalidTransition, State, transition
from sibylle.domain.permissions import Action, can
from sibylle.domain.settlement import BetLine, Entry, Outcome, refunds, settle, winners_by_options
from sibylle.realtime import bus
from sibylle.services import ledger, notifications
from sibylle.services.pronos import (
    get_prono,
    live_settlement,
    record_event,
    result_label,
    set_state,
)


@dataclass(frozen=True)
class Result:
    """What a journalist designates: the correct options, or the real number or date."""

    correct_option_ids: list[uuid.UUID] | None = None
    result_number: Decimal | None = None
    result_date: date | None = None


async def _locked(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, action: Action
) -> Prono:
    if not can(member.role, action):
        raise AppError("forbidden")
    return await get_prono(session, member, prono_id, lock=True)


def _next_state(prono: Prono, event: Event) -> State:
    try:
        return transition(
            State(prono.state), event, open_ended=prono.open_ended, bet_count=prono.bet_count
        )
    except InvalidTransition as error:
        raise AppError("invalid_state") from error


async def _options(session: AsyncSession, prono: Prono) -> list[PronoOption]:
    return list(
        (
            await session.scalars(
                select(PronoOption)
                .where(PronoOption.prono_id == prono.id)
                .order_by(PronoOption.position)
            )
        ).all()
    )


def _checked(prono: Prono, options: list[PronoOption], result: Result) -> dict[str, Any]:
    """The result as stored in `settlements.result`, or a validation error."""
    match Kind(prono.kind):
        case Kind.CHOICE | Kind.YES_NO:
            ids = set(result.correct_option_ids or [])
            if not ids:
                raise AppError("validation_error", {"correct_option_ids": "missing"})
            if not ids <= {o.id for o in options}:
                raise AppError("validation_error", {"correct_option_ids": "unknown"})
            return {"correct_option_ids": sorted(str(i) for i in ids)}
        case Kind.NUMBER:
            if result.result_number is None:
                raise AppError("validation_error", {"result_number": "missing"})
            return {"number": str(result.result_number.quantize(Decimal("0.01")))}
        case Kind.DATE:
            if result.result_date is None:
                raise AppError("validation_error", {"result_date": "missing"})
            return {"date": result.result_date.isoformat()}


def _apply(prono: Prono, options: list[PronoOption], stored: dict[str, Any]) -> None:
    correct = set(stored.get("correct_option_ids", []))
    for option in options:
        option.is_correct = str(option.id) in correct if correct else None
    prono.result_number = Decimal(stored["number"]) if "number" in stored else None
    prono.result_date = date.fromisoformat(stored["date"]) if "date" in stored else None


async def _bets(session: AsyncSession, prono: Prono) -> list[Bet]:
    return list(
        await session.scalars(select(Bet).where(Bet.prono_id == prono.id).order_by(Bet.rank))
    )


def _line(bet: Bet) -> BetLine:
    return BetLine(
        id=bet.id,
        member_id=bet.membership_id,
        stake=bet.stake,
        rank=bet.rank,
        active=bet.superseded_at is None,
        option_id=bet.option_id,
        value=bet.number_value if bet.number_value is not None else bet.date_value,
    )


async def _lock_members(session: AsyncSession, member_ids: set[uuid.UUID]) -> None:
    # Always in the same order, so two settlements touching the same members cannot deadlock.
    if member_ids:
        await session.execute(
            select(Membership.id)
            .where(Membership.id.in_(member_ids))
            .order_by(Membership.id)
            .with_for_update()
        )


async def _new_settlement(
    session: AsyncSession, prono: Prono, kind: str, actor: Membership, result: dict[str, Any]
) -> Settlement:
    last = await session.scalar(
        select(func.max(Settlement.seq)).where(Settlement.prono_id == prono.id)
    )
    settlement = Settlement(
        prono_id=prono.id, seq=(last or 0) + 1, kind=kind, result=result, created_by=actor.id
    )
    session.add(settlement)
    await session.flush()
    return settlement


async def _write(
    session: AsyncSession,
    entries: tuple[Entry, ...],
    prono: Prono,
    settlement: Settlement,
    actor: Membership,
) -> None:
    for entry in entries:
        await ledger.append(
            session,
            entry.member_id,
            entry.effect,
            prono_id=prono.id,
            bet_id=entry.bet_id,
            settlement_id=settlement.id,
            actor_membership_id=actor.id,
        )


async def _reverse_payouts(
    session: AsyncSession, previous: Settlement, settlement: Settlement, actor: Membership
) -> None:
    """Undoes what the previous settlement paid. Its own reversals stay: they undid an older one."""
    entries = (
        await session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.settlement_id == previous.id,
                LedgerEntry.kind != LedgerKind.REVERSAL.value,
            )
            .order_by(LedgerEntry.id)
        )
    ).all()
    for entry in entries:
        await ledger.reverse(
            session, entry, settlement_id=settlement.id, actor_membership_id=actor.id
        )
    previous.reversed_by_id = settlement.id


async def _pay(
    session: AsyncSession,
    prono: Prono,
    bets: list[Bet],
    stored: dict[str, Any],
    settlement: Settlement,
    actor: Membership,
) -> Outcome:
    lines = [_line(bet) for bet in bets]
    if "number" in stored:
        winners = closest(lines, Decimal(stored["number"]))
    elif "date" in stored:
        winners = closest(lines, date.fromisoformat(stored["date"]))
    else:
        ids = {uuid.UUID(i) for i in stored["correct_option_ids"]}
        winners = winners_by_options(lines, ids)
    org = await session.get(Organisation, prono.org_id)
    assert org is not None
    outcome = settle(
        lines,
        winners,
        base_gain=prono.base_gain,
        early_bird_pct=org.early_bird_pct,
        early_bird_count=org.early_bird_count,
    )
    await _write(session, outcome.entries, prono, settlement, actor)
    payouts = {p.bet_id: p.total for p in outcome.payouts}
    now = clock.now()
    for bet in bets:
        bet.outcome = "won" if bet.id in payouts else "lost"
        bet.payout = payouts.get(bet.id, 0)
        bet.settled_at = now
    return outcome


async def _announce(
    session: AsyncSession,
    prono: Prono,
    settlement: Settlement,
    bets: list[Bet],
    options: list[PronoOption],
) -> None:
    """Tells the screens, and each member who bet (US8 « résultat »)."""
    await session.flush()
    await notifications.prono_settled(
        session, prono, settlement, bets, result_label(prono, options)
    )
    await bus.publish(
        session,
        "prono.resolved",
        {"prono_id": str(prono.id), "settlement_seq": settlement.seq, "kind": settlement.kind},
        topics=[f"org:{prono.org_id}", f"prono:{prono.id}"],
    )
    await bus.publish(session, "leaderboard.changed", {}, topics=[f"org:{prono.org_id}"])


async def resolve(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, result: Result
) -> Prono:
    prono = await _locked(session, member, prono_id, Action.DESIGNATE_RESULT)
    state = _next_state(prono, Event.RESOLVE)
    options = await _options(session, prono)
    stored = _checked(prono, options, result)
    bets = await _bets(session, prono)
    await _lock_members(session, {bet.membership_id for bet in bets})

    _apply(prono, options, stored)
    settlement = await _new_settlement(session, prono, "resolution", member, stored)
    await _pay(session, prono, bets, stored, settlement, member)
    prono.resolved_at = clock.now()
    prono.resolved_by = member.id
    await set_state(session, prono, state, "resolved", member, {"result": stored})
    await _announce(session, prono, settlement, bets, options)
    return prono


async def correct(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, result: Result
) -> Prono:
    prono = await _locked(session, member, prono_id, Action.CORRECT_RESULT)
    _next_state(prono, Event.CORRECT)
    options = await _options(session, prono)
    stored = _checked(prono, options, result)
    previous = await live_settlement(session, prono.id)
    assert previous is not None, "a resolved prono has a settlement"
    if previous.result == stored:
        raise AppError("validation_error", {"result": "unchanged"})
    bets = await _bets(session, prono)
    await _lock_members(session, {bet.membership_id for bet in bets})

    _apply(prono, options, stored)
    settlement = await _new_settlement(session, prono, "correction", member, stored)
    await _reverse_payouts(session, previous, settlement, member)
    await _pay(session, prono, bets, stored, settlement, member)
    prono.resolved_at = clock.now()
    prono.resolved_by = member.id
    await record_event(
        session, prono, "corrected", member, {"previous": previous.result, "result": stored}
    )
    await _announce(session, prono, settlement, bets, options)
    return prono


async def cancel(
    session: AsyncSession, member: Membership, prono_id: uuid.UUID, reason: str | None
) -> Prono:
    prono = await _locked(session, member, prono_id, Action.CANCEL_PRONO)
    state = _next_state(prono, Event.CANCEL)
    previous = await live_settlement(session, prono.id)
    bets = await _bets(session, prono)
    await _lock_members(session, {bet.membership_id for bet in bets})

    settlement = await _new_settlement(session, prono, "cancellation", member, {})
    if previous is not None:
        await _reverse_payouts(session, previous, settlement, member)
    await _write(session, refunds(_line(bet) for bet in bets), prono, settlement, member)
    now = clock.now()
    for bet in bets:
        bet.outcome = "refunded"
        bet.payout = 0
        bet.settled_at = now
    prono.cancelled_at = now
    prono.cancelled_by = member.id
    await set_state(session, prono, state, "cancelled", member, {"reason": reason})
    await _announce(session, prono, settlement, bets, [])
    return prono


async def relaunch(
    session: AsyncSession,
    member: Membership,
    prono_id: uuid.UUID,
    *,
    closes_at: datetime,
    result_expected_at: datetime | None,
    reason: str | None,
) -> Prono:
    """A postponed event: the prono opens again until a new closing time, bets kept."""
    prono = await _locked(session, member, prono_id, Action.RELAUNCH_PRONO)
    state = _next_state(prono, Event.RELAUNCH)
    if closes_at <= clock.now():
        raise AppError("validation_error", {"closes_at": "in_past"})
    if result_expected_at is not None and result_expected_at < closes_at:
        raise AppError("validation_error", {"result_expected_at": "before_closing"})
    previous = prono.closes_at
    prono.closes_at = closes_at
    prono.result_expected_at = result_expected_at
    prono.relaunch_count += 1
    await set_state(
        session,
        prono,
        state,
        "relaunched",
        member,
        {
            "previous_closes_at": previous.isoformat() if previous else None,
            "closes_at": closes_at.isoformat(),
            "reason": reason,
        },
    )
    return prono
