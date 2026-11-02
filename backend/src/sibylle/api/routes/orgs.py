"""Newsrooms: creating one, reading one, and the editor's settings (card, laurels, access code,
sections)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from sibylle.api.deps import CurrentAccount, CurrentMember, Db, require
from sibylle.api.errors import AppError
from sibylle.api.schemas import (
    AccessCodeOut,
    MemberSelf,
    Org,
    OrgCreated,
    OrgIn,
    OrgPatch,
    SectionIn,
    SectionOut,
    SectionPatch,
    drawing,
)
from sibylle.db.models import Membership, Organisation
from sibylle.domain.permissions import Action
from sibylle.services import orgs

router = APIRouter(prefix="/orgs", tags=["orgs"])

Editor = Annotated[Membership, Depends(require(Action.CUSTOMIZE_CARD))]
Gatekeeper = Annotated[Membership, Depends(require(Action.MANAGE_MEMBERS))]
SectionEditor = Annotated[Membership, Depends(require(Action.MANAGE_SECTIONS))]


async def _org(session: Db, org_id: uuid.UUID) -> Organisation:
    org = await session.get(Organisation, org_id)
    if org is None:
        raise AppError("not_found")
    return org


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
    org = await _org(session, org_id)
    return Org.build(
        org,
        member,
        await orgs.member_count(session, org_id),
        await orgs.unlocked_colors(session, member),
    )


@router.patch("/{org_id}")
async def update_org(org_id: uuid.UUID, body: OrgPatch, editor: Editor, session: Db) -> Org:
    changes = body.model_dump(exclude_unset=True)
    if "logo" in body.model_fields_set:
        changes["logo"] = drawing(body.logo)
    org = await orgs.update_settings(session, await _org(session, org_id), changes)
    return Org.build(
        org,
        editor,
        await orgs.member_count(session, org_id),
        await orgs.unlocked_colors(session, editor),
    )


@router.post("/{org_id}/access-code")
async def renew_access_code(org_id: uuid.UUID, editor: Gatekeeper, session: Db) -> AccessCodeOut:
    code = await orgs.renew_access_code(session, await _org(session, org_id))
    return AccessCodeOut(access_code=code)


@router.delete("/{org_id}/access-code", status_code=204)
async def disable_access_code(org_id: uuid.UUID, editor: Gatekeeper, session: Db) -> Response:
    await orgs.disable_access_code(session, await _org(session, org_id))
    return Response(status_code=204)


@router.get("/{org_id}/sections")
async def list_sections(org_id: uuid.UUID, member: CurrentMember, session: Db) -> list[SectionOut]:
    return [SectionOut.model_validate(s) for s in await orgs.active_sections(session, org_id)]


@router.post("/{org_id}/sections", status_code=201)
async def create_section(
    org_id: uuid.UUID, body: SectionIn, editor: SectionEditor, session: Db
) -> SectionOut:
    return SectionOut.model_validate(await orgs.create_section(session, org_id, body.name))


@router.patch("/{org_id}/sections/{section_id}")
async def update_section(
    org_id: uuid.UUID,
    section_id: uuid.UUID,
    body: SectionPatch,
    editor: SectionEditor,
    session: Db,
) -> SectionOut:
    section = await orgs.update_section(
        session, org_id, section_id, name=body.name, position=body.position
    )
    return SectionOut.model_validate(section)


@router.delete("/{org_id}/sections/{section_id}", status_code=204)
async def delete_section(
    org_id: uuid.UUID, section_id: uuid.UUID, editor: SectionEditor, session: Db
) -> Response:
    await orgs.delete_section(session, org_id, section_id)
    return Response(status_code=204)
