"""Members' reports about a prono: a wrong result or an unwelcome content."""

import uuid

from fastapi import APIRouter

from sybille.api.deps import CurrentMember, Db
from sybille.api.schemas import ReportIn, ReportOut
from sybille.services import reports

router = APIRouter(prefix="/orgs/{org_id}/pronos/{prono_id}", tags=["reports"])


@router.post("/reports", status_code=201)
async def create_report(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: ReportIn, member: CurrentMember, session: Db
) -> ReportOut:
    report = await reports.create_report(session, member, prono_id, body.kind, body.message)
    return ReportOut.model_validate(report)
