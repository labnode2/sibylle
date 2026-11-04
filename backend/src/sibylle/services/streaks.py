"""Chains of wins, computed on demand from the settled bets (research.md J8).

A bet counts once its prono is settled, if it is still the member's bet in force and it won or
lost. The bets follow the order of the first settlement of their prono: its UUIDv7 keeps the
order of writing, and a correction changes the outcome without moving the prono."""

import uuid

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle.db.models import Bet, Membership, Settlement
from sibylle.domain.streaks import Streak, streak

_FIRST_SETTLEMENT = and_(Settlement.prono_id == Bet.prono_id, Settlement.seq == 1)


def _settled() -> ColumnElement[bool]:
    return and_(Bet.superseded_at.is_(None), Bet.outcome.in_(("won", "lost")))


async def current(session: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Each member's chain under way; a member without any is missing (counts 0)."""
    # 1 for the latest result, 2 for the one before…: the chain is the wins before the first loss.
    recency = func.row_number().over(partition_by=Bet.membership_id, order_by=Settlement.id.desc())
    results = (
        select(
            Bet.membership_id.label("member_id"),
            (Bet.outcome == "won").label("won"),
            recency.label("recency"),
        )
        .join(Membership, Membership.id == Bet.membership_id)
        .join(Settlement, _FIRST_SETTLEMENT)
        .where(Membership.org_id == org_id, _settled())
        .subquery()
    )
    chain = func.coalesce(
        func.min(results.c.recency).filter(results.c.won.is_(False)) - 1, func.count()
    )
    rows = await session.execute(select(results.c.member_id, chain).group_by(results.c.member_id))
    return {member_id: int(value) for member_id, value in rows}


async def of_member(session: AsyncSession, member: Membership) -> Streak:
    """A member's chain under way and their record, for their press card."""
    wins = await session.scalars(
        select(Bet.outcome == "won")
        .join(Settlement, _FIRST_SETTLEMENT)
        .where(Bet.membership_id == member.id, _settled())
        .order_by(Settlement.id)
    )
    return streak(wins)
