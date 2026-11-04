"""US13: the chain of wins of each member, in the leaderboard, on la une, in the member list and
on the press card (spec FR-074, FR-075, research.md J8)."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import MakeMember, MakeOrg, MakePerson, Person
from tests.contract.helpers import assert_no_private_data
from tests.contract.test_leaderboard import settle
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url

from sibylle import clock

pytestmark = pytest.mark.contract


async def chains(client: httpx.AsyncClient, org_id: str) -> dict[str, int]:
    """Each member's chain, as the leaderboard, la une and the member list give it."""
    response = await client.get(f"/api/orgs/{org_id}/leaderboard")
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()["rows"]
    board = {row["member"]["pseudo"]: row["streak"] for row in rows}

    members = await client.get(f"/api/orgs/{org_id}/members")
    assert members.status_code == 200, members.text
    assert_no_private_data(members.json())
    assert {m["pseudo"]: m["streak"] for m in members.json()} == board

    front = (await client.get(f"/api/orgs/{org_id}/front-page")).json()
    for row in front["leaderboard_top"]:
        assert row["streak"] == board[row["member"]["pseudo"]]
    return board


async def card(client: httpx.AsyncClient, org_id: str, member: Person) -> tuple[int, int]:
    response = await client.get(f"/api/orgs/{org_id}/members/{member.member.id}")
    assert response.status_code == 200, response.text
    stats: dict[str, int] = response.json()["stats"]
    return stats["streak"], stats["best_streak"]


async def play(
    journalist: httpx.AsyncClient,
    org_id: str,
    answers: list[tuple[Person, str]],
    result: str | None,
) -> dict[str, Any]:
    """A prono on which each person bets their answer, then settled on `result` (left closed
    without a result when it is None)."""
    prono = await publish(journalist, org_id)
    for who, answer in answers:
        bet = await place(who.client, org_id, prono["id"], option_id=option(prono, answer), stake=0)
        assert bet.status_code == 201, bet.text
    if result is not None:
        await settle(journalist, org_id, prono, result)
    return prono


async def test_a_chain_of_wins_lights_up_and_a_loss_puts_it_out(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    org_id = str(org.id)
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")

    await play(hugo.client, org_id, [(cami, "Nice"), (leo, "Monaco")], "Nice")
    await play(hugo.client, org_id, [(cami, "Nice"), (leo, "Monaco")], "Nice")
    assert await chains(cami.client, org_id) == {"Inès": 0, "Hugo": 0, "Cami": 2, "Léo": 0}

    # A prono she did not play, and one cancelled, leave her chain alone.
    await play(hugo.client, org_id, [(leo, "Monaco")], "Monaco")
    cancelled = await play(hugo.client, org_id, [(cami, "Monaco"), (leo, "Monaco")], None)
    response = await ines.client.post(url(org_id, cancelled["id"], "cancel"), json={})
    assert response.status_code == 200, response.text
    await play(hugo.client, org_id, [(cami, "Nice")], "Nice")
    assert await chains(leo.client, org_id) == {"Inès": 0, "Hugo": 0, "Cami": 3, "Léo": 1}
    assert await card(leo.client, org_id, cami) == (3, 3)

    # A loss puts it out; the record stays.
    await play(hugo.client, org_id, [(cami, "Monaco")], "Nice")
    assert (await chains(cami.client, org_id))["Cami"] == 0
    assert await card(cami.client, org_id, cami) == (0, 3)
    assert await card(cami.client, org_id, hugo) == (0, 0)


async def test_a_corrected_result_keeps_its_place_in_the_chain(
    make_org: MakeOrg, person: MakePerson, make_member: MakeMember, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    org_id = str(org.id)
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")

    await play(hugo.client, org_id, [(cami, "Nice")], "Nice")
    second = await play(hugo.client, org_id, [(cami, "Nice"), (leo, "Monaco")], "Nice")
    await play(hugo.client, org_id, [(cami, "Nice")], "Nice")
    assert (await chains(cami.client, org_id))["Cami"] == 3

    # The second result was Monaco after all: Cami lost it where it stood, between two wins.
    corrected = await ines.client.post(
        url(org_id, second["id"], "correct"),
        json={"correct_option_ids": [option(second, "Monaco")]},
    )
    assert corrected.status_code == 200, corrected.text
    assert await chains(cami.client, org_id) == {"Inès": 0, "Hugo": 0, "Cami": 1, "Léo": 1}
    assert await card(cami.client, org_id, cami) == (1, 1)

    # Her chain belongs to this newsroom: in another one, she starts from nothing.
    other = await make_org("Le Petit Écho")
    await make_member(other, "reader", account=cami.account, pseudo="Cami")
    assert await chains(cami.client, str(other.id)) == {"Cami": 0}


async def test_only_the_bet_in_force_counts(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await play(hugo.client, org_id, [(cami, "Nice")], "Nice")

    # An open-ended date: her first date passed, she bets again and the new date is right. The
    # replaced bet loses, but it is not hers to count any more.
    prono = await publish(
        hugo.client, org_id, kind="date", options=[], open_ended=True, closes_at=None
    )
    tomorrow = (clock.now() + timedelta(days=1)).date().isoformat()
    first = await place(cami.client, org_id, prono["id"], date_value=tomorrow, stake=0)
    assert first.status_code == 201, first.text
    fake_clock.advance(timedelta(days=2))
    later = (clock.now() + timedelta(days=3)).date().isoformat()
    again = await place(cami.client, org_id, prono["id"], date_value=later, stake=0)
    assert again.status_code == 201, again.text
    resolved = await hugo.client.post(
        url(org_id, prono["id"], "resolve"), json={"result_date": later}
    )
    assert resolved.status_code == 200, resolved.text

    assert (await chains(cami.client, org_id))["Cami"] == 2
    assert await card(cami.client, org_id, cami) == (2, 2)
