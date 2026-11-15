from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import update
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import assert_no_private_data
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url

from sibylle import clock
from sibylle.db.models import Membership
from sibylle.db.session import transaction
from sibylle.domain.ledger import adjustment
from sibylle.services import ledger
from sibylle.worker.jobs import advance_pronos, close_finished_seasons

pytestmark = pytest.mark.contract

PARIS = ZoneInfo("Europe/Paris")


async def board(
    client: httpx.AsyncClient, org_id: object, metric: str, period: str
) -> list[tuple[int, str, int, bool]]:
    response = await client.get(
        f"/api/orgs/{org_id}/leaderboard", params={"metric": metric, "period": period}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert_no_private_data(body)
    return [(r["rank"], r["member"]["pseudo"], r["value"], r["is_me"]) for r in body["rows"]]


async def label(client: httpx.AsyncClient, org_id: object, period: str) -> str:
    response = await client.get(
        f"/api/orgs/{org_id}/leaderboard", params={"metric": "wins", "period": period}
    )
    value: str = response.json()["period_label"]
    return value


async def settle(
    journalist: httpx.AsyncClient, org_id: str, prono: dict[str, Any], answer: str
) -> None:
    clock.fake_clock().advance(timedelta(days=4))
    await advance_pronos()
    response = await journalist.post(
        url(org_id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, answer)]}
    )
    assert response.status_code == 200, response.text


async def test_the_rankings_across_months_and_seasons(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")
    paul = await person(org, "reader", "Paul")
    zoe = await person(org, "reader", "Zoé")

    # November: Cami wins against Léo and Paul (+20 base, the pot of 20).
    november = await publish(hugo.client, org_id)
    await place(cami.client, org_id, november["id"], option_id=option(november, "Nice"), stake=10)
    await place(leo.client, org_id, november["id"], option_id=option(november, "Monaco"), stake=5)
    await place(paul.client, org_id, november["id"], option_id=option(november, "Nul"), stake=5)
    await settle(hugo.client, org_id, november, "Nice")
    # Paul leaves and Zoé deletes her account: neither is ranked any more.
    async with transaction() as session:
        await session.execute(
            update(Membership).where(Membership.id == paul.member.id).values(status="left")
        )
        await session.execute(
            update(Membership).where(Membership.id == zoe.member.id).values(status="anonymized")
        )

    # December: Léo wins, Manon loses 10, Cami's free bet is lost.
    fake_clock.set(datetime(2026, 12, 2, 10, tzinfo=PARIS))
    december = await publish(hugo.client, org_id)
    await place(leo.client, org_id, december["id"], option_id=option(december, "Nice"), stake=10)
    await place(
        manon.client, org_id, december["id"], option_id=option(december, "Monaco"), stake=10
    )
    await place(cami.client, org_id, december["id"], option_id=option(december, "Nul"), stake=0)
    await settle(hugo.client, org_id, december, "Nice")

    # The editor's adjustment counts too.
    async with transaction() as session:
        await ledger.append(session, cami.member.id, adjustment(-30), reason="Erreur")

    # The gold laurels: the balance, plus the stakes in play.
    gold_now = await board(cami.client, org.id, "laurels", "all_time")
    assert gold_now == sorted(gold_now, key=lambda r: r[0])
    assert {r[1]: r[2] for r in gold_now} == {"Cami": 100, "Hugo": 100, "Léo": 125, "Manon": 90}
    assert await board(cami.client, org.id, "wins", "month") == [
        (1, "Léo", 1, False),
        (2, "Cami", 0, True),
        (2, "Hugo", 0, False),
        (2, "Manon", 0, False),
    ]
    assert await board(leo.client, org.id, "wins", "season") == [
        (1, "Cami", 1, False),
        (1, "Léo", 1, True),
        (3, "Hugo", 0, False),
        (3, "Manon", 0, False),
    ]
    assert await label(cami.client, org.id, "month") == "2026-12"
    assert await label(cami.client, org.id, "season") == "2026-autumn"
    assert await label(cami.client, org.id, "all_time") == "all_time"

    current = (await cami.client.get(f"/api/orgs/{org_id}/seasons/current")).json()
    assert (current["year"], current["name"]) == (2026, "autumn")
    assert datetime.fromisoformat(current["ends_at"]) == datetime(2026, 12, 21, tzinfo=PARIS)

    # Winter: the closure resets everyone's gold laurels to the starting balance.
    fake_clock.set(datetime(2026, 12, 21, 0, 0, 30, tzinfo=PARIS))
    assert await close_finished_seasons() == 1
    rows = await board(cami.client, org.id, "laurels", "all_time")
    assert [r[0] for r in rows] == sorted(r[0] for r in rows)
    assert await board(cami.client, org.id, "wins", "all_time") == [
        (1, "Cami", 1, True),
        (1, "Léo", 1, False),
        (3, "Hugo", 0, False),
        (3, "Manon", 0, False),
    ]
    # December still counts Léo's win from before the closure.
    assert (await board(cami.client, org.id, "wins", "month"))[0] == (1, "Léo", 1, False)
    current = (await cami.client.get(f"/api/orgs/{org_id}/seasons/current")).json()
    assert (current["year"], current["name"]) == (2026, "winter")


async def test_laurels_rank_by_gold_laurels(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    rich = await person(org, "reader", "Rich")
    poor = await person(org, "reader", "Poor")
    async with transaction() as session:
        await ledger.append(session, rich.member.id, adjustment(500), reason="Bonus")
        await ledger.append(session, poor.member.id, adjustment(-60), reason="Perdu")
    rows = await board(rich.client, org.id, "laurels", "all_time")
    assert rows == [(1, "Rich", 600, True), (2, "Poor", 40, False)]


async def test_gold_laurels_count_stakes_in_play(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=30)
    rows = await board(cami.client, org.id, "laurels", "all_time")
    assert (1, "Cami", 100, True) in rows


async def test_invalid_metric_or_period(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org)
    for params in (
        {"metric": "score", "period": "month"},
        {"metric": "wins", "period": "week"},
        # The gold laurels are a total as of now: all time only.
        {"metric": "laurels", "period": "month"},
        {"metric": "laurels", "period": "season"},
    ):
        response = await cami.client.get(f"/api/orgs/{org.id}/leaderboard", params=params)
        assert response.status_code == 422, response.text


async def test_outsiders_get_404(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    await person(org)
    outsider = await person(await make_org("Autre rédaction"))
    for path in (
        f"/api/orgs/{org.id}/leaderboard?metric=laurels&period=all_time",
        f"/api/orgs/{org.id}/seasons/current",
    ):
        assert (await outsider.client.get(path)).status_code == 404
