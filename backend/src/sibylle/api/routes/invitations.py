"""Inviting people (the editor) and joining a newsroom (anyone signed in)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from sibylle.api.deps import CurrentAccount, Db, Limits, client_ip, limits, require
from sibylle.api.errors import AppError
from sibylle.api.schemas import (
    InvitationCreated,
    InvitationIn,
    InvitationOut,
    Joined,
    JoinIn,
    JoinPreview,
    JoinSource,
    LinkInvitationIn,
    MemberSelf,
    OrgCard,
)
from sibylle.db.models import Invitation, Membership, Organisation
from sibylle.domain.permissions import Action
from sibylle.services import invitations

router = APIRouter(tags=["invitations"])

Inviter = Annotated[Membership, Depends(require(Action.MANAGE_MEMBERS))]


def invitation_out(invitation: Invitation) -> InvitationOut:
    return InvitationOut.model_validate(
        {
            **{c: getattr(invitation, c) for c in InvitationOut.model_fields if c != "places_left"},
            "places_left": invitations.places_left(invitation),
        }
    )


@router.post("/orgs/{org_id}/invitations", status_code=201)
async def create_invitation(
    org_id: uuid.UUID, body: InvitationIn, member: Inviter, session: Db
) -> InvitationCreated:
    org = await session.get(Organisation, org_id)
    if org is None:
        raise AppError("not_found")
    if isinstance(body, LinkInvitationIn):
        invitation, token = await invitations.create_link(
            session, member, max_uses=body.max_uses, expires_at=body.expires_at
        )
        return InvitationCreated(
            invitation=invitation_out(invitation), url=invitations.join_url(token)
        )
    invitation = await invitations.create_email_invitation(session, member, org, body.email)
    return InvitationCreated(invitation=invitation_out(invitation), url=None)


@router.post("/join/preview")
async def preview_join(body: JoinSource, account: CurrentAccount, session: Db) -> JoinPreview:
    data = await invitations.preview(session, account, token=body.token, code=body.code)
    return JoinPreview(**{**data, "org": OrgCard.of(data["org"])})


@router.post("/join", status_code=201)
async def join(
    body: JoinIn,
    request: Request,
    account: CurrentAccount,
    session: Db,
    rate: Annotated[Limits, Depends(limits)],
) -> Joined:
    rate.join.hit(f"ip:{client_ip(request)}")
    org, member = await invitations.join(
        session,
        account,
        token=body.token,
        code=body.code,
        pseudo=body.pseudo,
        avatar=body.avatar.model_dump(),
    )
    return Joined(org=OrgCard.of(org), membership=MemberSelf.of(member))
