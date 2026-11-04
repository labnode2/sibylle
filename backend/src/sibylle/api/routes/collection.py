"""The collection: the catalog, purchases with coins and secret codes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from sibylle.api.deps import CurrentMember, Db, Limits, limits
from sibylle.api.schemas import (
    CatalogEntry,
    CatalogItemOut,
    OwnedItemOut,
    PurchaseIn,
    PurchaseOut,
    RedeemIn,
    RedeemOut,
)
from sibylle.services import collection, deals

router = APIRouter(prefix="/orgs/{org_id}", tags=["collection"])


@router.get("/catalog")
async def get_catalog(org_id: uuid.UUID, member: CurrentMember, session: Db) -> list[CatalogEntry]:
    deal = await deals.this_week(session, member.org_id)
    entries = []
    for item, owned in await collection.catalog(session, member):
        sale = deal if deals.on_sale(item, deal) else None
        entries.append(
            CatalogEntry(
                item=CatalogItemOut.model_validate(item),
                price=deals.price_of(item, deal),
                regular_price=item.price if sale else None,
                discount_pct=sale.discount_pct if sale else None,
                discount_until=deals.ends_at() if sale else None,
                owned=owned,
            )
        )
    return entries


@router.post("/catalog/{item_id}/purchase", status_code=201)
async def purchase(
    org_id: uuid.UUID,
    item_id: uuid.UUID,
    member: CurrentMember,
    session: Db,
    body: PurchaseIn | None = None,
) -> PurchaseOut:
    owned, item, coins = await collection.buy(
        session, member, item_id, shown_price=body.price if body else None
    )
    return PurchaseOut(
        owned_item=OwnedItemOut(
            item=CatalogItemOut.model_validate(item),
            source=owned.source,
            acquired_at=owned.acquired_at,
        ),
        coins=coins,
    )


@router.post("/secret-codes/redeem", status_code=201)
async def redeem_secret_code(
    org_id: uuid.UUID,
    body: RedeemIn,
    member: CurrentMember,
    session: Db,
    rate: Annotated[Limits, Depends(limits)],
) -> RedeemOut:
    # Every try counts, right or wrong: codes cannot be guessed one after another.
    rate.secret_code.hit(f"member:{member.id}")
    item = await collection.redeem(session, member, body.code)
    return RedeemOut(item=CatalogItemOut.model_validate(item))
