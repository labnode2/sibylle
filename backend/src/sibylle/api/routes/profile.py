"""A member's press card."""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from sibylle.api.deps import CurrentMember, Db
from sibylle.api.errors import AppError
from sibylle.api.schemas import CatalogItemOut, MemberPublic, OwnedItemOut, PressCard
from sibylle.db.models import Membership
from sibylle.services import collection

router = APIRouter(prefix="/orgs/{org_id}/members", tags=["profile"])


@router.get("/{member_id}")
async def get_press_card(
    org_id: uuid.UUID, member_id: uuid.UUID, member: CurrentMember, session: Db
) -> PressCard:
    other = await session.scalar(
        select(Membership).where(
            Membership.id == member_id,
            Membership.org_id == org_id,
            Membership.status == "active",
        )
    )
    if other is None:
        raise AppError("not_found")
    card = await collection.press_card(session, other)
    return PressCard(
        **MemberPublic.of(other).model_dump(),
        card_number=card["card_number"],
        stats=card["stats"],
        trophies=card["trophies"],
        collection=[
            OwnedItemOut(
                item=CatalogItemOut.model_validate(item),
                source=owned.source,
                acquired_at=owned.acquired_at,
            )
            for owned, item in card["collection"]
        ],
    )
