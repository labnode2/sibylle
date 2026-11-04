"""The games of each week (US12, research.md J7): the editor plans the current week and the
three after it; a week without a planning of its own takes the games of an ordinary week, a
setting dated by the Monday from which it holds.

This module keeps the planning only: `minigames` reads it, and `minigames.follow_schedule` makes
Pixel mystère follow a change of the current week.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.api.errors import AppError
from sibylle.db.models import GameDefault, GameWeek
from sibylle.domain.game_schedule import (
    Game,
    horizon,
    normalized,
    ordinary_games,
    week_games,
    week_problem,
)
from sibylle.domain.seasons import week_start
from sibylle.realtime import bus


async def games_of(session: AsyncSession, org_id: uuid.UUID, week: date) -> tuple[Game, ...]:
    """A newsroom's games for the week starting on that Monday."""
    planned = await session.scalar(
        select(GameWeek.games).where(GameWeek.org_id == org_id, GameWeek.week_start == week)
    )
    if planned is not None:
        return normalized(planned)
    in_force = await session.execute(
        select(GameDefault.from_week, GameDefault.games)
        .where(GameDefault.org_id == org_id, GameDefault.from_week <= week)
        .order_by(GameDefault.from_week.desc())
        .limit(1)
    )
    return ordinary_games(in_force.all(), week)


async def schedule(session: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """What the editor sees: an ordinary week from next week on, then the current week and the
    three after it, each with its games and whether it has a planning of its own."""
    weeks = horizon(clock.now())
    planned = dict(
        (
            await session.execute(
                select(GameWeek.week_start, GameWeek.games).where(
                    GameWeek.org_id == org_id, GameWeek.week_start.in_(weeks)
                )
            )
        ).all()
    )
    defaults = (
        await session.execute(
            select(GameDefault.from_week, GameDefault.games).where(
                GameDefault.org_id == org_id, GameDefault.from_week <= weeks[-1]
            )
        )
    ).all()
    return {
        "default": ordinary_games(defaults, weeks[1]),
        "weeks": [
            {
                "week_start": week,
                "games": week_games(week, planned, defaults),
                "planned": week in planned,
            }
            for week in weeks
        ],
    }


async def set_ordinary(session: AsyncSession, org_id: uuid.UUID, games: Sequence[str]) -> None:
    """Sets the games of an ordinary week from next week on; the weeks already begun keep theirs,
    so that the race's Monday payment and the week in play never change behind the editor."""
    statement = insert(GameDefault).values(
        org_id=org_id,
        from_week=horizon(clock.now())[1],
        games=list(normalized(games)),
        updated_at=clock.now(),
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[GameDefault.org_id, GameDefault.from_week],
            set_={"games": statement.excluded.games, "updated_at": statement.excluded.updated_at},
        )
    )


def _checked(week: date) -> None:
    """A Monday among the four weeks the editor plans, or 422."""
    problem = week_problem(week, clock.now())
    if problem is not None:
        raise AppError("validation_error", {"week_start": problem})


async def plan_week(
    session: AsyncSession, org_id: uuid.UUID, week: date, games: Sequence[str]
) -> bool:
    """Gives a week games of its own. Returns whether the current week's games changed: the
    caller then makes Pixel mystère follow (`minigames.follow_schedule`)."""
    _checked(week)
    chosen = normalized(games)
    current = week == week_start(clock.now())
    before = await games_of(session, org_id, week) if current else None
    statement = insert(GameWeek).values(
        org_id=org_id, week_start=week, games=list(chosen), updated_at=clock.now()
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[GameWeek.org_id, GameWeek.week_start],
            set_={"games": statement.excluded.games, "updated_at": statement.excluded.updated_at},
        )
    )
    if not current or before == chosen:
        return False
    await bus.publish(
        session,
        "games.schedule.changed",
        {"week_start": week.isoformat(), "games": list(chosen)},
        topics=[f"org:{org_id}"],
    )
    return True


async def unplan_week(session: AsyncSession, org_id: uuid.UUID, week: date) -> None:
    """An upcoming week goes back to an ordinary week. The current week keeps the games it
    began with: the editor changes them one by one instead."""
    _checked(week)
    if week == week_start(clock.now()):
        raise AppError("invalid_state")
    await session.execute(
        delete(GameWeek).where(GameWeek.org_id == org_id, GameWeek.week_start == week)
    )
