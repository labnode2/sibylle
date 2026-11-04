"""The games of the week: the ball's race (US9), Pixel mystère (US10) and their planning (US12)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle.api.deps import CurrentMember, Db, require
from sibylle.api.errors import AppError
from sibylle.api.schemas import (
    Games,
    GameSchedule,
    GamesIn,
    PixelGuessIn,
    PixelGuessOut,
    PixelPuzzleIn,
    PixelQueueItem,
    PixelStatus,
    RunFinished,
    RunFinishIn,
    RunStarted,
)
from sibylle.db.models import Membership
from sibylle.domain.permissions import Action
from sibylle.services import game_schedule, minigames

router = APIRouter(prefix="/orgs/{org_id}/games", tags=["games"])

Planner = Annotated[Membership, Depends(require(Action.SCHEDULE_GAMES))]


@router.get("")
async def get_games(org_id: uuid.UUID, member: CurrentMember, session: Db) -> Games:
    return Games.model_validate(await minigames.games(session, member))


@router.post("/runner/runs", status_code=201)
async def start_run(org_id: uuid.UUID, member: CurrentMember, session: Db) -> RunStarted:
    run = await minigames.start_run(session, member)
    return RunStarted(run_id=run.id, seed=run.seed)


@router.post("/runner/runs/{run_id}/finish")
async def finish_run(
    org_id: uuid.UUID, run_id: uuid.UUID, body: RunFinishIn, member: CurrentMember, session: Db
) -> RunFinished:
    result = await minigames.finish_run(session, member, run_id, body.score, body.duration_ms)
    return RunFinished.model_validate(result)


@router.get("/pixel")
async def get_pixel(org_id: uuid.UUID, member: CurrentMember, session: Db) -> PixelStatus | None:
    status = await minigames.pixel_status(session, member)
    return PixelStatus.model_validate(status) if status else None


@router.post("/pixel/guesses")
async def guess(
    org_id: uuid.UUID, body: PixelGuessIn, member: CurrentMember, session: Db
) -> PixelGuessOut:
    return PixelGuessOut.model_validate(await minigames.guess(session, member, body.word))


@router.get("/pixel/puzzles")
async def get_queue(org_id: uuid.UUID, member: CurrentMember, session: Db) -> list[PixelQueueItem]:
    return [PixelQueueItem.model_validate(item) for item in await minigames.queue(session, member)]


@router.post("/pixel/puzzles", status_code=201)
async def post_puzzle(
    org_id: uuid.UUID, body: PixelPuzzleIn, member: CurrentMember, session: Db
) -> PixelQueueItem:
    puzzle = await minigames.post_puzzle(session, member, body.drawing.model_dump(), body.word)
    mine = next(
        (item for item in await minigames.queue(session, member) if item["puzzle_id"] == puzzle.id),
        None,
    )
    if mine is None:
        raise AppError("not_found")
    return PixelQueueItem.model_validate(mine)


async def _schedule(session: AsyncSession, editor: Membership) -> GameSchedule:
    return GameSchedule.model_validate(await game_schedule.schedule(session, editor.org_id))


@router.get("/schedule")
async def get_schedule(org_id: uuid.UUID, editor: Planner, session: Db) -> GameSchedule:
    return await _schedule(session, editor)


@router.put("/schedule/default")
async def put_ordinary_week(
    org_id: uuid.UUID, body: GamesIn, editor: Planner, session: Db
) -> GameSchedule:
    await game_schedule.set_ordinary(session, editor.org_id, body.games)
    return await _schedule(session, editor)


@router.put("/schedule/weeks/{week_start}")
async def put_week(
    org_id: uuid.UUID, week_start: date, body: GamesIn, editor: Planner, session: Db
) -> GameSchedule:
    if await game_schedule.plan_week(session, editor.org_id, week_start, body.games):
        await minigames.follow_schedule(session, editor.org_id)
    return await _schedule(session, editor)


@router.delete("/schedule/weeks/{week_start}")
async def delete_week(
    org_id: uuid.UUID, week_start: date, editor: Planner, session: Db
) -> GameSchedule:
    await game_schedule.unplan_week(session, editor.org_id, week_start)
    return await _schedule(session, editor)
