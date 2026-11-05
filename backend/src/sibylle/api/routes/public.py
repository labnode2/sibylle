"""What anyone may see without an account: a press card its member made public (US15)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from sibylle.api.deps import Db, Limits, client_ip, limits
from sibylle.api.schemas import PressStats, PublicCard, PublicNewsroom, ShowcaseOut
from sibylle.services import collection

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/cards/{token}")
async def get_public_card(
    token: Annotated[str, Path(max_length=64)],
    request: Request,
    session: Db,
    rate: Annotated[Limits, Depends(limits)],
) -> PublicCard:
    rate.public_card.hit(f"ip:{client_ip(request)}")
    org, member = await collection.public_card(session, token)
    face = await collection.card_face(session, member)
    return PublicCard(
        newsroom=PublicNewsroom.model_validate(org, from_attributes=True),
        pseudo=member.pseudo,
        avatar=member.avatar,
        frame=member.frame,
        role=member.role,
        joined_at=member.joined_at,
        card_number=face["card_number"],
        stats=PressStats.model_validate(face["stats"]),
        showcase=[ShowcaseOut.of(entry) for entry in face["showcase"]],
    )
