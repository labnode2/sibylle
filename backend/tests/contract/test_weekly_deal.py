"""The deal of the week in the collection (spec FR-095, research.md J10)."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import give_coins

from sibylle import clock
from sibylle.db.models import CatalogItem, CoinEntry, WeeklyDeal
from sibylle.db.session import transaction
from sibylle.domain.deals import DISCOUNTS, deal_price
from sibylle.domain.seasons import week_bounds, week_start
from sibylle.services import deals

pytestmark = pytest.mark.contract


async def catalog(client: httpx.AsyncClient, org_id: object) -> list[dict[str, Any]]:
    response = await client.get(f"/api/orgs/{org_id}/catalog")
    assert response.status_code == 200, response.text
    entries: list[dict[str, Any]] = response.json()
    return entries


def on_sale(entries: list[dict[str, Any]]) -> dict[str, Any]:
    [deal] = [entry for entry in entries if entry["discount_pct"] is not None]
    return deal


async def test_one_deal_a_week_the_same_for_the_whole_newsroom(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")

    # Two first looks at once: a single draw.
    first, seen_by_leo = await asyncio.gather(
        catalog(cami.client, org.id), catalog(leo.client, org.id)
    )
    deal = on_sale(first)
    assert on_sale(seen_by_leo)["item"]["id"] == deal["item"]["id"]
    assert deal["item"]["kind"] in ("color", "frame")
    assert deal["discount_pct"] in DISCOUNTS
    assert deal["regular_price"] == deal["item"]["price"]
    assert deal["price"] == deal_price(deal["regular_price"], deal["discount_pct"])
    _, next_monday = week_bounds(clock.now())
    assert datetime.fromisoformat(deal["discount_until"]) == next_monday
    for entry in first:
        if entry is not deal and entry["item"]["price"] is not None:
            assert entry["price"] == entry["item"]["price"]
            assert (entry["regular_price"], entry["discount_until"]) == (None, None)
    # The same all week.
    fake_clock.advance(timedelta(days=3))
    assert on_sale(await catalog(cami.client, org.id)) == deal

    # Next Monday, a new draw.
    fake_clock.advance(timedelta(days=4))
    later = on_sale(await catalog(cami.client, org.id))
    assert datetime.fromisoformat(later["discount_until"]) == next_monday + timedelta(days=7)
    async with transaction() as session:
        weeks = await session.scalar(
            select(func.count()).select_from(WeeklyDeal).where(WeeklyDeal.org_id == org.id)
        )
    assert weeks == 2


async def test_only_colours_and_frames_go_on_sale(make_org: MakeOrg) -> None:
    async with transaction() as session:
        candidates = await deals.candidates(session)
    assert candidates
    assert {item.kind for item in candidates} <= {"color", "frame"}
    assert all(item.price for item in candidates)
    # The draw itself picks one of them, and one of the shares off.
    for _ in range(20):
        item, discount_pct = deals._draw(candidates)
        assert item in candidates and discount_pct in DISCOUNTS


async def test_the_deal_is_paid_at_its_price(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    # This week's draw: the bright red, at 30 %.
    async with transaction() as session:
        red = await session.scalar(select(CatalogItem).where(CatalogItem.key == "color-41"))
        assert red is not None and red.price == 400
        session.add(
            WeeklyDeal(
                org_id=org.id, week_start=week_start(clock.now()), item_id=red.id, discount_pct=30
            )
        )
    await give_coins(cami.member, 300)

    deal = on_sale(await catalog(cami.client, org.id))
    assert (deal["item"]["key"], deal["price"], deal["regular_price"]) == ("color-41", 280, 400)
    purchase = f"/api/orgs/{org.id}/catalog/{deal['item']['id']}/purchase"
    # A price the screen showed before the week changed is refused.
    stale = await cami.client.post(purchase, json={"price": 400})
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "price_changed")
    bought = await cami.client.post(purchase, json={"price": 280})
    assert bought.status_code == 201, bought.text
    assert bought.json()["coins"] == 20
    async with transaction() as session:
        paid = await session.scalar(
            select(CoinEntry.amount).where(
                CoinEntry.membership_id == cami.member.id, CoinEntry.kind == "purchase"
            )
        )
    assert paid == -280

    # Everything else costs its usual price: 400 coins for a colour she cannot afford now.
    entries = await catalog(cami.client, org.id)
    other = next(
        e for e in entries if e["item"]["kind"] == "color" and not e["owned"] and e["price"]
    )
    assert other["price"] == other["item"]["price"] == 400
    refused = await cami.client.post(f"/api/orgs/{org.id}/catalog/{other['item']['id']}/purchase")
    assert refused.json()["error"]["code"] == "insufficient_coins"
