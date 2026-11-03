"""The games of the week: the ball's race (US9) and Pixel mystère (US10)."""

import uuid

from fastapi import APIRouter

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.errors import AppError
from sibylle.api.schemas import (
    Games,
    PixelGuessIn,
    PixelGuessOut,
    PixelPuzzleIn,
    PixelQueueItem,
    PixelStatus,
    RunFinished,
    RunFinishIn,
    RunnerStatus,
    RunStarted,
)
from sibylle.services import minigames

router = APIRouter(prefix="/orgs/{org_id}/games", tags=["games"])


@router.get("")
async def get_games(org_id: uuid.UUID, member: CurrentMember, session: Db) -> Games:
    runner = await minigames.runner_status(session, member)
    pixel = await minigames.pixel_status(session, member)
    return Games(
        runner=RunnerStatus.model_validate(runner),
        pixel=PixelStatus.model_validate(pixel) if pixel else None,
    )


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
