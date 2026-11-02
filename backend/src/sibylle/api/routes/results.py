"""Designating a prono's result, relaunching, correcting and cancelling it."""

import uuid

from fastapi import APIRouter

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.schemas import CancelIn, PronoDetail, RelaunchIn, ResultIn
from sibylle.services import pronos, results

router = APIRouter(prefix="/orgs/{org_id}/pronos/{prono_id}", tags=["results"])


def _result(body: ResultIn) -> results.Result:
    return results.Result(
        correct_option_ids=body.correct_option_ids,
        result_number=body.result_number,
        result_date=body.result_date,
    )


@router.post("/resolve")
async def resolve(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: ResultIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await results.resolve(session, member, prono_id, _result(body))
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.post("/correct")
async def correct(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: ResultIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await results.correct(session, member, prono_id, _result(body))
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.post("/relaunch")
async def relaunch(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: RelaunchIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await results.relaunch(
        session,
        member,
        prono_id,
        closes_at=body.closes_at,
        result_expected_at=body.result_expected_at,
        reason=body.reason,
    )
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))


@router.post("/cancel")
async def cancel(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: CancelIn, member: CurrentMember, session: Db
) -> PronoDetail:
    prono = await results.cancel(session, member, prono_id, body.reason)
    return PronoDetail.model_validate(await pronos.detail(session, member, prono))
