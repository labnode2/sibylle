"""The deal of the week (research.md J10): in each newsroom, one colour or frame on sale at a
share off, drawn at random on the week's first look at the collection (or first purchase), then
kept until Sunday night, whatever happens to the catalog meanwhile."""

import random
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.db.models import CatalogItem, WeeklyDeal
from sibylle.domain.deals import DISCOUNTS, deal_price
from sibylle.domain.seasons import week_bounds, week_start

_DRAW = random.SystemRandom()


def _draw(items: Sequence[CatalogItem]) -> tuple[CatalogItem, int]:
    return _DRAW.choice(items), _DRAW.choice(DISCOUNTS)


# The draw of an object and its share off; the tests put a known deal in its place.
pick: Callable[[Sequence[CatalogItem]], tuple[CatalogItem, int]] = _draw


async def candidates(session: AsyncSession) -> list[CatalogItem]:
    """What may go on sale: the colours and frames that have a price (balls are never sold)."""
    return list(
        (
            await session.scalars(
                select(CatalogItem)
                .where(
                    CatalogItem.active,
                    CatalogItem.price.is_not(None),
                    CatalogItem.kind.in_(("color", "frame")),
                )
                .order_by(CatalogItem.key)
            )
        ).all()
    )


async def this_week(session: AsyncSession, org_id: uuid.UUID) -> WeeklyDeal | None:
    """The newsroom's deal of the week, drawn now if nobody looked yet; several first looks at
    once still make a single draw."""
    week = week_start(clock.now())
    query = select(WeeklyDeal).where(WeeklyDeal.org_id == org_id, WeeklyDeal.week_start == week)
    deal = await session.scalar(query)
    if deal is not None:
        return deal
    items = await candidates(session)
    if not items:
        return None
    item, discount_pct = pick(items)
    await session.execute(
        insert(WeeklyDeal)
        .values(
            org_id=org_id,
            week_start=week,
            item_id=item.id,
            discount_pct=discount_pct,
            created_at=clock.now(),
        )
        .on_conflict_do_nothing()
    )
    return await session.scalar(query.execution_options(populate_existing=True))


def on_sale(item: CatalogItem, deal: WeeklyDeal | None) -> bool:
    return deal is not None and deal.item_id == item.id and item.price is not None


def price_of(item: CatalogItem, deal: WeeklyDeal | None) -> int | None:
    """The item's price this week: the deal's, or its usual price; None if it is not sold."""
    if item.price is not None and deal is not None and deal.item_id == item.id:
        return deal_price(item.price, deal.discount_pct)
    return item.price


def ends_at() -> datetime:
    """The end of the week's deal: next Monday 00:00, in Paris."""
    return week_bounds(clock.now())[1]
