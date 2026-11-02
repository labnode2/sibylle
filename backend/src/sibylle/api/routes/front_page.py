"""La une of a newsroom."""

import uuid

from fastapi import APIRouter

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import FrontPage
from sibylle.services.front_page import front_page

router = APIRouter(prefix="/orgs/{org_id}", tags=["front page"])


@router.get("/front-page")
async def get_front_page(org_id: uuid.UUID, member: CurrentMember, session: Db) -> FrontPage:
    return FrontPage.model_validate(await front_page(session, member))
