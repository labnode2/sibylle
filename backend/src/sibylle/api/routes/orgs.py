"""Newsrooms: creating one, reading one."""

import uuid

from fastapi import APIRouter

from sibylle.api.deps import CurrentAccount, CurrentMember, Db
from sibylle.api.errors import AppError
from sibylle.api.schemas import MemberSelf, Org, OrgCreated, OrgIn, drawing
from sibylle.db.models import Organisation
from sibylle.services import orgs

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("", status_code=201)
async def create_org(body: OrgIn, account: CurrentAccount, session: Db) -> OrgCreated:
    org, member = await orgs.create_org(
        session,
        account,
        title=body.title,
        background_key=body.background_key,
        logo=drawing(body.logo),
        pseudo=body.pseudo,
        avatar=body.avatar.model_dump(),
    )
    return OrgCreated(org=Org.build(org, member, 1), membership=MemberSelf.of(member))


@router.get("/{org_id}")
async def get_org(org_id: uuid.UUID, member: CurrentMember, session: Db) -> Org:
    org = await session.get(Organisation, org_id)
    if org is None:
        raise AppError("not_found")
    return Org.build(org, member, await orgs.member_count(session, org_id))
