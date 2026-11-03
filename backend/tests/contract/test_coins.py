"""Coins (spec FR-094 to FR-096, research.md J6): Monday's conversion of gold laurels, the good
news shown once, and the member's three counters."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select, update
from tests.conftest import MakeOrg, MakePerson
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option

from sibylle import clock
from sibylle.db.models import CoinEntry, Membership
from sibylle.db.session import transaction
from sibylle.worker.jobs import grant_weekly_coins

pytestmark = pytest.mark.contract

PARIS = ZoneInfo("Europe/Paris")
WEDNESDAY = datetime(2026, 11, 4, 10, 0, tzinfo=PARIS)
MONDAY = datetime(2026, 11, 9, 0, 0, 30, tzinfo=PARIS)
NEXT_MONDAY = datetime(2026, 11, 16, 0, 0, 30, tzinfo=PARIS)


async def mine(client: httpx.AsyncClient, org_id: object) -> dict[str, Any]:
    body: dict[str, Any] = (await client.get(f"/api/orgs/{org_id}")).json()["my_membership"]
    return body


async def weekly(client: httpx.AsyncClient, org_id: object) -> Any:
    response = await client.get(f"/api/orgs/{org_id}/coins/weekly")
    assert response.status_code == 200, response.text
    return response.json()


async def seen(client: httpx.AsyncClient, org_id: object, week_start: str) -> httpx.Response:
    return await client.post(
        f"/api/orgs/{org_id}/coins/weekly/seen", json={"week_start": week_start}
    )


async def test_monday_turns_gold_laurels_into_coins(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(WEDNESDAY)
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    staked = await place(
        cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=30
    )
    assert staked.status_code == 201, staked.text

    # Green laurels can be staked; gold ones count the stake still in play.
    me = await mine(cami.client, org.id)
    assert (me["balance"], me["gold"], me["coins"]) == (70, 100, 0)

    # They all arrived after this week's Monday: nothing before the next one.
    assert await grant_weekly_coins() == 0
    async with transaction() as session:
        await session.execute(
            update(Membership).where(Membership.id == leo.member.id).values(status="left")
        )

    fake_clock.set(MONDAY)
    latecomer = await person(org, "reader", "Manon")
    assert await grant_weekly_coins() == 2  # Hugo and Cami; Léo left, Manon came too late
    assert await grant_weekly_coins() == 0  # once a week, even when run again

    me = await mine(cami.client, org.id)
    assert (me["balance"], me["gold"], me["coins"]) == (70, 100, 100)
    assert (await mine(hugo.client, org.id))["coins"] == 100
    assert (await mine(latecomer.client, org.id))["coins"] == 0
    statement = (await cami.client.get(f"/api/orgs/{org.id}/members/me/ledger")).json()["items"]
    assert "weekly" not in {entry["kind"] for entry in statement}

    # The good news, until Cami has seen it.
    assert await weekly(cami.client, org.id) == {
        "week_start": "2026-11-09",
        "gold": 100,
        "amount": 100,
    }
    assert await weekly(latecomer.client, org.id) is None
    tuesday = await seen(cami.client, org.id, "2026-11-10")
    assert tuesday.status_code == 422
    assert tuesday.json()["error"]["fields"] == {"week_start": "not_monday"}
    future = await seen(cami.client, org.id, "2026-11-16")
    assert future.json()["error"]["fields"] == {"week_start": "in_future"}
    assert (await seen(cami.client, org.id, "2026-11-09")).status_code == 204
    assert await weekly(cami.client, org.id) is None
    assert await weekly(hugo.client, org.id) is not None


async def test_gold_laurels_below_zero_give_nothing(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(WEDNESDAY)
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    # A correction left Léo in debt.
    async with transaction() as session:
        await session.execute(
            update(Membership).where(Membership.id == leo.member.id).values(balance=-15)
        )

    fake_clock.set(MONDAY)
    assert await grant_weekly_coins() == 2
    assert (await mine(leo.client, org.id))["coins"] == 0
    assert await weekly(leo.client, org.id) is None
    async with transaction() as session:
        entry = await session.scalar(
            select(CoinEntry).where(CoinEntry.membership_id == leo.member.id)
        )
    assert entry is not None and (entry.amount, entry.gold) == (0, -15)

    # Coins add up week after week; the news shows the latest Monday not seen yet.
    fake_clock.set(NEXT_MONDAY)
    assert await grant_weekly_coins() == 2
    assert (await mine(cami.client, org.id))["coins"] == 200
    assert (await weekly(cami.client, org.id))["week_start"] == "2026-11-16"
    assert (await seen(cami.client, org.id, "2026-11-16")).status_code == 204
    assert await weekly(cami.client, org.id) is None


async def test_coin_entries_cannot_be_changed(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    fake_clock.set(WEDNESDAY)
    org = await make_org()
    await person(org, "reader", "Cami")
    fake_clock.set(MONDAY)
    assert await grant_weekly_coins() == 1
    with pytest.raises(Exception, match="append-only"):
        async with transaction() as session:
            await session.execute(update(CoinEntry).values(amount=1000))
