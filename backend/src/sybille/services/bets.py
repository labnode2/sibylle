"""Placing a bet (research.md R11): lock the prono, then the member, check, write, tell."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sybille import clock
from sybille.api.errors import AppError
from sybille.db.models import Bet, Membership, PronoOption
from sybille.domain.betting import Answer, BetRefused, Kind, check_bet
from sybille.domain.ledger import stake as stake_effect
from sybille.domain.lifecycle import State
from sybille.domain.seasons import PARIS
from sybille.realtime import bus
from sybille.services import ledger
from sybille.services.pronos import bet_view, get_prono


async def place_bet(
    session: AsyncSession,
    member: Membership,
    prono_id: uuid.UUID,
    *,
    option_id: uuid.UUID | None,
    number_value: Decimal | None,
    date_value: date | None,
    stake: int,
) -> Bet:
    # Lock order: the prono, then the member. Two bets on the same prono wait for each other,
    # which keeps ranks gapless and stops a member from betting twice.
    prono = await get_prono(session, member, prono_id, lock=True)
    member = await ledger.lock_member(session, member.id)

    labels = {
        o.id: o.label
        for o in (
            await session.scalars(select(PronoOption).where(PronoOption.prono_id == prono.id))
        ).all()
    }
    if option_id is not None and option_id not in labels:
        raise AppError("validation_error", {"option_id": "unknown"})
    active = await session.scalar(
        select(Bet).where(
            Bet.prono_id == prono.id,
            Bet.membership_id == member.id,
            Bet.superseded_at.is_(None),
        )
    )
    now = clock.now()
    try:
        check_bet(
            state=State(prono.state),
            kind=Kind(prono.kind),
            open_ended=prono.open_ended,
            closes_at=prono.closes_at,
            now=now,
            today=now.astimezone(PARIS).date(),
            balance=member.balance,
            stake=stake,
            answer=Answer(option_id=option_id, number_value=number_value, date_value=date_value),
            has_active_bet=active is not None,
            active_bet_date=active.date_value if active else None,
        )
    except BetRefused as refused:
        raise AppError(refused.code, refused.fields) from refused

    if active is not None:
        # A new date on an open-ended prono: the previous bet steps aside; its stake stays
        # in the pot.
        active.superseded_at = now
        await session.flush()
    bet = Bet(
        prono_id=prono.id,
        membership_id=member.id,
        option_id=option_id,
        number_value=number_value,
        date_value=date_value,
        stake=stake,
        rank=prono.bet_count + 1,
        placed_at=now,
    )
    session.add(bet)
    await session.flush()
    if active is not None:
        active.superseded_by_id = bet.id
    prono.bet_count += 1
    prono.pot += stake
    if stake:
        await ledger.append(
            session, member.id, stake_effect(stake), prono_id=prono.id, bet_id=bet.id
        )
    await session.flush()

    view = bet_view(bet, prono, member, labels)
    await bus.publish(
        session,
        "bet.placed",
        {"bet": view, "pot": prono.pot, "bet_count": prono.bet_count},
        topics=[f"prono:{prono.id}"],
    )
    await bus.publish(
        session,
        "bet.placed",
        {"prono_id": str(prono.id), "pot": prono.pot, "bet_count": prono.bet_count},
        topics=[f"org:{prono.org_id}"],
    )
    return bet
