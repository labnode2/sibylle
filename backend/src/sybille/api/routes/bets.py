"""Betting on a prono."""

import uuid

from fastapi import APIRouter

from sybille.api.deps import CurrentMember, Db
from sybille.api.schemas import BetIn, BetOut
from sybille.db.models import PronoOption
from sybille.services import bets, pronos

router = APIRouter(prefix="/orgs/{org_id}/pronos/{prono_id}", tags=["bets"])


@router.post("/bets", status_code=201)
async def place_bet(
    org_id: uuid.UUID, prono_id: uuid.UUID, body: BetIn, member: CurrentMember, session: Db
) -> BetOut:
    bet = await bets.place_bet(
        session,
        member,
        prono_id,
        option_id=body.option_id,
        number_value=body.number_value,
        date_value=body.date_value,
        stake=body.stake,
    )
    prono = await pronos.get_prono(session, member, prono_id)
    option = await session.get(PronoOption, bet.option_id) if bet.option_id else None
    labels = {option.id: option.label} if option else {}
    return BetOut.model_validate(pronos.bet_view(bet, prono, member, labels))
