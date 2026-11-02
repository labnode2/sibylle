"""Reports: a member flags a wrong result or a content about a prono; the editor handles them."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from sibylle.api.deps import CurrentMember, Db, require
from sibylle.api.schemas import (
    HandleIn,
    MemberPublic,
    PronoRef,
    ReportDetail,
    ReportIn,
    ReportOut,
)
from sibylle.db.models import Membership
from sibylle.domain.permissions import Action
from sibylle.services import reports

router = APIRouter(prefix="/orgs/{org_id}", tags=["reports"])

Moderator = Annotated[Membership, Depends(require(Action.HANDLE_REPORTS))]


@router.post("/pronos/{prono_id}/reports", status_code=201)
async def create_report(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: ReportIn, member: CurrentMember, session: Db
) -> ReportOut:
    report = await reports.create_report(session, member, prono_id, body.kind, body.message)
    return ReportOut.model_validate(report)


@router.get("/reports")
async def list_reports(
    org_id: uuid.UUID,
    editor: Moderator,
    session: Db,
    state: Literal["open", "resolved", "dismissed"] | None = None,
) -> list[ReportDetail]:
    return [
        ReportDetail.model_validate(
            {
                **ReportOut.model_validate(report).model_dump(),
                "prono": PronoRef(id=prono.id, question=prono.question),
                "reporter": MemberPublic.of(author),
            }
        )
        for report, prono, author in await reports.list_reports(session, org_id, state)
    ]


@router.post("/reports/{report_id}/handle")
async def handle_report(
    org_id: uuid.UUID, report_id: uuid.UUID, body: HandleIn, editor: Moderator, session: Db
) -> ReportOut:
    report = await reports.handle_report(session, editor, report_id, body.state, body.note)
    return ReportOut.model_validate(report)
