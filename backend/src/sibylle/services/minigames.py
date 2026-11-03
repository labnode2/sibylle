"""The mini-games of the week: the ball's race (US9, research.md J3 and R19).

The server opens each run (seed, start) and counts the week's attempts; the game runs in the
browser and sends its score and duration, which the server checks before keeping them. On Monday,
the past week's ranking is paid to the balance, once per newsroom.
"""

import secrets
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import Membership, MinigamePayout, Organisation, RunnerRun
from sibylle.domain.ledger import minigame
from sibylle.domain.minigames import (
    RUN_MAX,
    RUNNER_ATTEMPTS,
    RunResult,
    plausible,
    rank_runner,
    runner_gains,
    week_to_pay,
)
from sibylle.domain.seasons import week_start
from sibylle.realtime import bus
from sibylle.services import ledger, seasons
from sibylle.services.orgs import public_member

TOP = 10
# The browser's clock and the server's may differ a little.
CLOCK_SLACK_MS = 2_000


async def _ranking(session: AsyncSession, org_id: uuid.UUID, week: date) -> list[RunResult]:
    """The week's finished runs of the newsroom's active members, best run each, best first."""
    rows = await session.execute(
        select(RunnerRun.membership_id, RunnerRun.score, RunnerRun.finished_at)
        .join(Membership, Membership.id == RunnerRun.membership_id)
        .where(
            RunnerRun.org_id == org_id,
            RunnerRun.week_start == week,
            RunnerRun.finished_at.is_not(None),
            RunnerRun.score > 0,
            Membership.status == "active",
        )
    )
    return rank_runner(
        RunResult(member_id, score, finished_at)
        for member_id, score, finished_at in rows
        if score is not None and finished_at is not None
    )


async def _top(session: AsyncSession, ranked: list[RunResult]) -> list[dict[str, Any]]:
    shown = ranked[:TOP]
    members = {
        member.id: member
        for member in await session.scalars(
            select(Membership).where(Membership.id.in_([run.member_id for run in shown]))
        )
    }
    return [
        {"member": members[run.member_id], "score": run.score, "rank": rank}
        for rank, run in enumerate(shown, start=1)
    ]


async def _attempts(session: AsyncSession, member: Membership, week: date) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(RunnerRun)
        .where(RunnerRun.membership_id == member.id, RunnerRun.week_start == week)
    )
    return int(count or 0)


async def runner_status(session: AsyncSession, member: Membership) -> dict[str, Any]:
    week = week_start(clock.now())
    ranked = await _ranking(session, member.org_id, week)
    mine = next((run for run in ranked if run.member_id == member.id), None)
    return {
        "week_start": week,
        "attempts_left": max(0, RUNNER_ATTEMPTS - await _attempts(session, member, week)),
        "my_best": mine.score if mine else None,
        "top": await _top(session, ranked),
    }


async def start_run(session: AsyncSession, member: Membership) -> RunnerRun:
    """Opens a run; it counts as an attempt even if it is never finished."""
    # One attempt at a time per member, so two taps cannot open a sixth run.
    await session.execute(select(Membership.id).where(Membership.id == member.id).with_for_update())
    week = week_start(clock.now())
    if await _attempts(session, member, week) >= RUNNER_ATTEMPTS:
        raise AppError("attempts_exhausted")
    run = RunnerRun(
        org_id=member.org_id,
        membership_id=member.id,
        week_start=week,
        seed=secrets.randbits(31),
    )
    session.add(run)
    await session.flush()
    return run


async def finish_run(
    session: AsyncSession, member: Membership, run_id: uuid.UUID, score: int, duration_ms: int
) -> dict[str, Any]:
    run = await session.scalar(
        select(RunnerRun)
        .where(RunnerRun.id == run_id, RunnerRun.membership_id == member.id)
        .with_for_update()
    )
    if run is None:
        raise AppError("not_found")
    if run.finished_at is not None:
        raise AppError("run_finished")
    now = clock.now()
    elapsed_ms = int((now - run.started_at).total_seconds() * 1000)
    if elapsed_ms > RUN_MAX.total_seconds() * 1000 + CLOCK_SLACK_MS:
        raise AppError("validation_error", {"duration_ms": "run_expired"})
    if duration_ms > elapsed_ms + CLOCK_SLACK_MS:
        raise AppError("validation_error", {"duration_ms": "longer_than_run"})
    if not plausible(score, duration_ms):
        raise AppError("validation_error", {"score": "implausible"})
    run.finished_at = now
    run.score = score
    run.duration_ms = duration_ms
    await session.flush()

    ranked = await _ranking(session, member.org_id, run.week_start)
    top = await _top(session, ranked)
    await bus.publish(
        session,
        "games.runner.updated",
        {
            "week_start": run.week_start.isoformat(),
            "top": [
                {"member": public_member(row["member"]), "score": row["score"], "rank": row["rank"]}
                for row in top
            ],
        },
        topics=[f"org:{member.org_id}"],
    )
    rank, best = next(
        ((i, r.score) for i, r in enumerate(ranked, start=1) if r.member_id == member.id),
        (None, score),
    )
    return {"score": score, "my_best": best, "rank": rank}


async def pay_runner_week(session: AsyncSession, *, org_id: uuid.UUID | None = None) -> int:
    """Pays the last finished week to each newsroom's players, once; returns how many were paid.

    A newsroom whose season closure is due waits for it, so that the season's reset never wipes
    the gains out. `org_id` keeps one newsroom only (tests on a shared database).
    """
    week = week_to_pay(clock.now())
    period = week.isoformat()
    newsroom = RunnerRun.org_id == org_id if org_id is not None else true()
    org_ids = (
        await session.scalars(
            select(RunnerRun.org_id)
            .join(Organisation, Organisation.id == RunnerRun.org_id)
            .where(
                newsroom,
                RunnerRun.week_start == week,
                RunnerRun.finished_at.is_not(None),
                Organisation.deleted_at.is_(None),
            )
            .distinct()
            .order_by(RunnerRun.org_id)
        )
    ).all()
    paid = 0
    for org in org_ids:
        if await seasons.due(session, org):
            continue
        claimed = await session.scalar(
            insert(MinigamePayout)
            .values(org_id=org, game="runner", period_key=period, paid_at=clock.now())
            .on_conflict_do_nothing()
            .returning(MinigamePayout.org_id)
        )
        if claimed is None:
            continue
        gains = runner_gains(await _ranking(session, org, week))
        # Locked in id order, like the settlements, so that both cannot deadlock.
        await session.execute(
            select(Membership.id)
            .where(Membership.id.in_([member_id for member_id, _ in gains]))
            .order_by(Membership.id)
            .with_for_update()
        )
        for member_id, gain in gains:
            await ledger.append(session, member_id, minigame(gain), reason=f"runner:{period}")
        paid += len(gains)
    return paid
