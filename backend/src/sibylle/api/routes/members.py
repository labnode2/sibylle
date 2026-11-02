"""A newsroom's members, as the other members see them."""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.errors import AppError
from sibylle.api.schemas import MemberPatch, MemberPublic, MemberSelf, drawing
from sibylle.db.models import Membership
from sibylle.services import orgs

router = APIRouter(prefix="/orgs/{org_id}/members", tags=["members"])


@router.get("")
async def list_members(org_id: uuid.UUID, member: CurrentMember, session: Db) -> list[MemberPublic]:
    return [MemberPublic.of(m) for m in await orgs.active_members(session, org_id)]


@router.patch("/me")
async def update_my_profile(
    org_id: uuid.UUID, body: MemberPatch, member: CurrentMember, session: Db
) -> MemberSelf:
    await orgs.update_profile(session, member, pseudo=body.pseudo, avatar=drawing(body.avatar))
    return MemberSelf.of(member)


@router.get("/{member_id}")
async def get_member(
    org_id: uuid.UUID, member_id: uuid.UUID, member: CurrentMember, session: Db
) -> MemberPublic:
    other = await session.scalar(
        select(Membership).where(
            Membership.id == member_id,
            Membership.org_id == org_id,
            Membership.status == "active",
        )
    )
    if other is None:
        raise AppError("not_found")
    return MemberPublic.of(other)
