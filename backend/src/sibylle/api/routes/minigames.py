"""The games of the week: the ball's race (US9)."""

import uuid

from fastapi import APIRouter

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import Games, RunFinished, RunFinishIn, RunnerStatus, RunStarted
from sibylle.services import minigames

router = APIRouter(prefix="/orgs/{org_id}/games", tags=["games"])


@router.get("")
async def get_games(org_id: uuid.UUID, member: CurrentMember, session: Db) -> Games:
    status = await minigames.runner_status(session, member)
    return Games(runner=RunnerStatus.model_validate(status))


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
