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

    # The laurels are the green ones of the wallet: the editor's adjustment counts too.
    async with transaction() as session:
        await ledger.append(session, cami.member.id, adjustment(-30), reason="Erreur")

    season = [(1, "Léo", 125, False), (2, "Cami", 100, True), (2, "Hugo", 100, False)]
    season.append((4, "Manon", 90, False))
    assert await board(cami.client, org.id, "laurels", "season") == season
    assert await board(cami.client, org.id, "laurels", "all_time") == season
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

    # Winter: everyone starts again from 100; all time adds the engraved gold laurels.
    fake_clock.set(datetime(2026, 12, 21, 0, 0, 30, tzinfo=PARIS))
    assert await close_finished_seasons() == 1
    assert [row[2] for row in await board(cami.client, org.id, "laurels", "season")] == [100] * 4
    assert await board(cami.client, org.id, "laurels", "all_time") == [
        (1, "Léo", 225, False),
        (2, "Cami", 200, True),
        (3, "Manon", 190, False),
        (4, "Hugo", 100, False),
    ]
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

    # A winter win adds to the engraved laurels.
    winter = await publish(hugo.client, org_id)
    await place(manon.client, org_id, winter["id"], option_id=option(winter, "Nice"), stake=0)
    await settle(hugo.client, org_id, winter, "Nice")
    assert await board(cami.client, org.id, "laurels", "all_time") == [
        (1, "Léo", 225, False),
        (2, "Manon", 210, False),
        (3, "Cami", 200, True),
        (4, "Hugo", 100, False),
    ]


async def test_invalid_metric_or_period(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org)
    for params in (
        {"metric": "score", "period": "month"},
        {"metric": "wins", "period": "week"},
        # The laurels are what a member has: no month for them.
        {"metric": "laurels", "period": "month"},
    ):
        response = await cami.client.get(f"/api/orgs/{org.id}/leaderboard", params=params)
        assert response.status_code == 422, response.text


async def test_outsiders_get_404(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    await person(org)
    outsider = await person(await make_org("Autre rédaction"))
    for path in (
        f"/api/orgs/{org.id}/leaderboard?metric=laurels&period=season",
        f"/api/orgs/{org.id}/seasons/current",
    ):
        assert (await outsider.client.get(path)).status_code == 404
