"""The newsroom's rankings and the current season."""

import uuid

from fastapi import APIRouter

from sibylle import clock
from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import Leaderboard, LeaderboardRow, MemberPublic, SeasonOut
from sibylle.domain.leaderboard import Metric, Period
from sibylle.domain.seasons import season_bounds, season_of
from sibylle.services import leaderboard, streaks

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
    chains = await streaks.current(session, org_id)
    return Leaderboard(
        period_label=board.period_label,
        rows=[
            LeaderboardRow(
                rank=line.rank,
                member=MemberPublic.of(line.member),
                value=line.value,
                is_me=line.member.id == member.id,
                streak=chains.get(line.member.id, 0),
            )
            for line in board.lines
        ],
    )


@router.get("/seasons/current")
async def current_season(org_id: uuid.UUID, member: CurrentMember) -> SeasonOut:
    key = season_of(clock.now())
    starts_at, ends_at = season_bounds(key.year, key.name)
    return SeasonOut(year=key.year, name=key.name, starts_at=starts_at, ends_at=ends_at)
