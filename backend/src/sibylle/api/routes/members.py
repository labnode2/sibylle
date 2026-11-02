"""A newsroom's members: as the other members see them, and as the editor manages them."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from sibylle.api.deps import CurrentMember, Db, require
from sibylle.api.errors import AppError
from sibylle.api.schemas import (
    AdjustmentIn,
    LedgerEntryOut,
    LedgerPage,
    MemberPatch,
    MemberPublic,
    MemberSelf,
    PronoRef,
    RoleIn,
    drawing,
)
from sibylle.db.models import LedgerEntry, Membership
from sibylle.domain.permissions import Action
from sibylle.services import ledger, orgs

router = APIRouter(prefix="/orgs/{org_id}/members", tags=["members"])

Gatekeeper = Annotated[Membership, Depends(require(Action.MANAGE_MEMBERS))]
Treasurer = Annotated[Membership, Depends(require(Action.ADJUST_LAURELS))]


def entry_out(entry: LedgerEntry, question: str | None) -> LedgerEntryOut:
    return LedgerEntryOut(
        id=entry.id,
        kind=entry.kind,
        amount=entry.amount,
        score_delta=entry.score_delta,
        reason=entry.reason,
        prono=PronoRef(id=entry.prono_id, question=question)
        if entry.prono_id and question
        else None,
        created_at=entry.created_at,
    )


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


@router.get("/me/ledger")
async def my_ledger(
    org_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LedgerPage:
    """The member's own statement: every movement of their laurels, newest first."""
    page, next_cursor = await ledger.statement(session, member.id, cursor=cursor, limit=limit)
    return LedgerPage(items=[entry_out(e, q) for e, q in page], next_cursor=next_cursor)


@router.patch("/{member_id}/role")
async def change_role(
    org_id: uuid.UUID, member_id: uuid.UUID, body: RoleIn, editor: Gatekeeper, session: Db
) -> MemberPublic:
    return MemberPublic.of(await orgs.change_role(session, org_id, member_id, body.role))


@router.delete("/{member_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID, member_id: uuid.UUID, editor: Gatekeeper, session: Db
) -> Response:
    await orgs.remove_member(session, org_id, member_id)
    return Response(status_code=204)


@router.post("/{member_id}/adjustments", status_code=201)
async def adjust_laurels(
    org_id: uuid.UUID, member_id: uuid.UUID, body: AdjustmentIn, editor: Treasurer, session: Db
) -> LedgerEntryOut:
    entry = await orgs.adjust_laurels(session, editor, member_id, body.amount, body.reason)
    return entry_out(entry, None)
