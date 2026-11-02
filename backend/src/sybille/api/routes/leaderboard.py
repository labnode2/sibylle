"""The newsroom's rankings and the current season."""

import uuid

from fastapi import APIRouter

from sybille import clock
from sybille.api.deps import CurrentMember, Db
from sybille.api.schemas import Leaderboard, LeaderboardRow, MemberPublic, SeasonOut
from sybille.domain.leaderboard import Metric, Period
from sybille.domain.seasons import season_bounds, season_of
from sybille.services import leaderboard

router = APIRouter(prefix="/orgs/{org_id}", tags=["leaderboard"])


@router.get("/leaderboard")
async def get_leaderboard(
    org_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
    metric: Metric = Metric.LAURELS,
    period: Period = Period.SEASON,
) -> Leaderboard:
    board = await leaderboard.board(session, org_id, metric, period)
    return Leaderboard(
        period_label=board.period_label,
        rows=[
            LeaderboardRow(
                rank=line.rank,
                member=MemberPublic.of(line.member),
                value=line.value,
                is_me=line.member.id == member.id,
            )
            for line in board.lines
        ],
    )


@router.get("/seasons/current")
async def current_season(org_id: uuid.UUID, member: CurrentMember) -> SeasonOut:
    key = season_of(clock.now())
    starts_at, ends_at = season_bounds(key.year, key.name)
    return SeasonOut(year=key.year, name=key.name, starts_at=starts_at, ends_at=ends_at)
