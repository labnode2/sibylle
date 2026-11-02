"""A newsroom's pronos."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import (
    PronoDetail,
    PronoIn,
    PronoList,
    PronoPatch,
    PronoSummary,
    ReactionKind,
    RejectIn,
    ValidateIn,
)
from sibylle.services import pronos

router = APIRouter(prefix="/orgs/{org_id}", tags=["pronos"])


@router.get("/pronos")
async def list_pronos(
    org_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
    state: Annotated[list[str], Query()] = [],  # noqa: B006 - FastAPI reads it, never mutated
    section: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PronoList:
    page, next_cursor = await pronos.list_pronos(
        session, member, states=state, section_id=section, cursor=cursor, limit=limit
    )
    items = [PronoSummary.model_validate(s) for s in await pronos.summaries(session, page)]
    return PronoList(items=items, next_cursor=next_cursor)


@router.post("/pronos", status_code=201)
async def create_prono(
    org_id: uuid.UUID, body: PronoIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await pronos.create_prono(session, member, body.model_dump())
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.get("/pronos/{prono_id}")
async def get_prono(
    org_id: uuid.UUID, prono_id: uuid.UUID, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await pronos.get_prono(session, member, prono_id)
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.patch("/pronos/{prono_id}")
async def edit_prono(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: PronoPatch, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await pronos.get_prono(session, member, prono_id, lock=True)
    await pronos.edit_prono(session, member, prono, body.model_dump(exclude_unset=True))
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.post("/pronos/{prono_id}/validate")
async def validate_proposal(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: ValidateIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await pronos.validate_proposal(session, member, prono_id, body.base_gain)
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.post("/pronos/{prono_id}/reject")
async def reject_proposal(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: RejectIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await pronos.reject_proposal(session, member, prono_id, body.reason or None)
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.put("/pronos/{prono_id}/reactions/{kind}", status_code=204)
async def add_reaction(
    org_id: uuid.UUID, prono_id: uuid.UUID, kind: ReactionKind, member: CurrentMember, session: Db
) -> Response:
    await pronos.react(session, member, prono_id, kind, on=True)
    return Response(status_code=204)


@router.delete("/pronos/{prono_id}/reactions/{kind}", status_code=204)
async def remove_reaction(
    org_id: uuid.UUID, prono_id: uuid.UUID, kind: ReactionKind, member: CurrentMember, session: Db
) -> Response:
    await pronos.react(session, member, prono_id, kind, on=False)
    return Response(status_code=204)
