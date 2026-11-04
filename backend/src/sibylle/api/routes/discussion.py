"""The discussion under a prono (US14): its messages, and their likes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import MessageIn, MessageOut, MessagePage
from sibylle.services import discussion

router = APIRouter(prefix="/orgs/{org_id}/pronos/{prono_id}/messages", tags=["discussion"])


@router.get("")
async def list_messages(
    org_id: uuid.UUID,
    prono_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
    before: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=discussion.PAGE_MAX)] = discussion.PAGE,
) -> MessagePage:
    items, has_more = await discussion.page(session, member, prono_id, before=before, limit=limit)
    return MessagePage(items=[MessageOut.model_validate(i) for i in items], has_more=has_more)


@router.post("", status_code=201)
async def write_message(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: MessageIn, member: CurrentMember, session: Db
) -> MessageOut:
    return MessageOut.model_validate(await discussion.write(session, member, prono_id, body.body))


@router.delete("/{message_id}", status_code=204)
async def delete_message(
    org_id: uuid.UUID,
    prono_id: uuid.UUID,
    message_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
) -> Response:
    await discussion.remove(session, member, prono_id, message_id)
    return Response(status_code=204)


@router.put("/{message_id}/like", status_code=204)
async def like_message(
    org_id: uuid.UUID,
    prono_id: uuid.UUID,
    message_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
) -> Response:
    await discussion.like(session, member, prono_id, message_id, on=True)
    return Response(status_code=204)


@router.delete("/{message_id}/like", status_code=204)
async def unlike_message(
    org_id: uuid.UUID,
    prono_id: uuid.UUID,
    message_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
) -> Response:
    await discussion.like(session, member, prono_id, message_id, on=False)
    return Response(status_code=204)
