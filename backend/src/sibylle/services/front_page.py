"""La une: the blocks of the front page, in the order of the spec (FR-080)."""

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle.db.models import Bet, Membership, Organisation, Prono, PronoOption
from sibylle.domain.leaderboard import Metric, Period
from sibylle.domain.lifecycle import State
from sibylle.domain.permissions import Action, can
from sibylle.services import leaderboard, pronos, streaks
from sibylle.services.orgs import public_member

OPEN_LIMIT = 12
RESULTS_LIMIT = 3
# Five on a computer; a phone shows the first three.
TOP = 5


async def _latest_results(session: AsyncSession, member: Membership) -> list[dict[str, Any]]:
    resolved = list(
        (
            await session.scalars(
                select(Prono)
                .where(pronos.visible_to(member), Prono.state == State.RESOLVED.value)
                .order_by(Prono.resolved_at.desc(), Prono.id)
                .limit(RESULTS_LIMIT)
            )
        ).all()
    )
    ids = [p.id for p in resolved]
    options: dict[Any, list[PronoOption]] = defaultdict(list)
    for option in (
        await session.scalars(select(PronoOption).where(PronoOption.prono_id.in_(ids)))
    ).all():
        options[option.prono_id].append(option)
    mine = {
        bet.prono_id: bet
        for bet in (
            await session.scalars(
                select(Bet).where(
                    Bet.prono_id.in_(ids),
                    Bet.membership_id == member.id,
                    Bet.superseded_at.is_(None),
                )
            )
        ).all()
    }
    return [
        {
            "prono": summary,
            "result": pronos.result_label(prono, options[prono.id]),
            "resolved_at": prono.resolved_at,
            "my_outcome": mine[prono.id].outcome if prono.id in mine else None,
            "my_payout": mine[prono.id].payout if prono.id in mine else None,
        }
        for prono, summary in zip(resolved, await pronos.summaries(session, resolved), strict=True)
    ]


async def _leaderboard_top(
    session: AsyncSession, member: Membership
) -> tuple[str, list[dict[str, Any]]]:
    """The season's first five by laurels, then the member's own line when they are not among
    them."""
    board = await leaderboard.board(session, member.org_id, Metric.LAURELS, Period.SEASON)
    lines = board.lines[:TOP]
    if all(line.member.id != member.id for line in lines):
        lines += [line for line in board.lines[TOP:] if line.member.id == member.id]
    chains = await streaks.current(session, member.org_id)
    return board.period_label, [
        {
            "rank": line.rank,
            "member": public_member(line.member),
            "value": line.value,
            "is_me": line.member.id == member.id,
            "streak": chains.get(line.member.id, 0),
        }
        for line in lines
    ]


async def front_page(session: AsyncSession, member: Membership) -> dict[str, Any]:
    org = await session.get(Organisation, member.org_id)
    assert org is not None
    # The one closing first is the headline; open-ended dates have no closing and come last.
    open_pronos = list(
        (
            await session.scalars(
                select(Prono)
                .where(pronos.visible_to(member), Prono.state == State.OPEN.value)
                .order_by(Prono.closes_at.asc().nulls_last(), Prono.created_at, Prono.id)
                .limit(OPEN_LIMIT + 1)
            )
        ).all()
    )
    summaries = await pronos.with_shares(session, open_pronos)
    open_count = await session.scalar(
        select(func.count())
        .select_from(Prono)
        .where(pronos.visible_to(member), Prono.state == State.OPEN.value)
    )
    to_designate = None
    if can(member.role, Action.DESIGNATE_RESULT):
        closed = list(
            (
                await session.scalars(
                    select(Prono)
                    .where(pronos.visible_to(member), Prono.state == State.CLOSED.value)
                    .order_by(Prono.closes_at, Prono.id)
                )
            ).all()
        )
        to_designate = await pronos.summaries(session, closed)
    period, top = await _leaderboard_top(session, member)
    return {
        "headline": summaries[0] if summaries else None,
        "open": summaries[1:],
        "open_count": open_count or 0,
        "to_designate": to_designate,
        "latest_results": await _latest_results(session, member),
        "leaderboard_top": top,
        "leaderboard_period": period,
        "editor_note": org.editor_note,
    }
