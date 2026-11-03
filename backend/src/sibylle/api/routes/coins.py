"""Coins: the news of Monday's conversion, until the member has seen it."""

import uuid

from fastapi import APIRouter

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import WeeklyCoins, WeeklySeenIn
from sibylle.services import coins

router = APIRouter(prefix="/orgs/{org_id}/coins", tags=["coins"])


@router.get("/weekly")
async def get_weekly(org_id: uuid.UUID, member: CurrentMember, session: Db) -> WeeklyCoins | None:
    entry = await coins.unannounced(session, member)
    return WeeklyCoins.model_validate(entry) if entry else None


@router.post("/weekly/seen", status_code=204)
async def weekly_seen(
    org_id: uuid.UUID, body: WeeklySeenIn, member: CurrentMember, session: Db
) -> None:
    await coins.mark_seen(session, member, body.week_start)
