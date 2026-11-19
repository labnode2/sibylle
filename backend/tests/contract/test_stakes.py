"""Stakes and shares (FR-041, FR-042): every new bet stakes at least one laurel, and the share of
each answer is that of the laurels staked on it, its number of people beside it. Bets placed
before the minimum with a stake of 0 stay as they were."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from tests.conftest import MakeOrg, MakePerson
from tests.contract.test_pronos import balance, place, publish
from tests.contract.test_results import caches_match, close, option, url

from sibylle import clock
from sibylle.db.models import Bet, Membership, Prono
from sibylle.db.session import transaction

pytestmark = pytest.mark.contract


def shares(prono: dict[str, Any]) -> list[tuple[str, int, int, int]]:
    """Each answer with its people, its laurels and its share."""
    return [(o["label"], o["count"], o["stake_total"], o["share_pct"]) for o in prono["options"]]


async def old_bet_without_stake(
    prono_id: str,
    member: Membership,
    *,
    option_id: str | None = None,
    number_value: Decimal | None = None,
    date_value: date | None = None,
) -> uuid.UUID:
    """A bet placed before the minimum stake, written as the server wrote it then: a stake of 0,
    no ledger entry, the prono's count up by one and its pot unchanged."""
    async with transaction() as session:
        prono = await session.get(Prono, uuid.UUID(prono_id), with_for_update=True)
        assert prono is not None
        prono.bet_count += 1
        bet = Bet(
            prono_id=prono.id,
            membership_id=member.id,
            option_id=uuid.UUID(option_id) if option_id else None,
            number_value=number_value,
            date_value=date_value,
            stake=0,
            rank=prono.bet_count,
        )
        session.add(bet)
        await session.flush()
        return bet.id


async def test_a_bet_stakes_at_least_one_laurel(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, org_id)
    nice = option(prono, "Nice")

    free = await place(cami.client, org_id, prono["id"], option_id=nice, stake=0)
    assert free.status_code == 422
    assert free.json()["error"]["code"] == "validation_error"
    assert free.json()["error"]["fields"] == {"stake": "too_low"}
    # A negative stake keeps the error it had.
    negative = await place(cami.client, org_id, prono["id"], option_id=nice, stake=-5)
    assert negative.status_code == 422
    assert negative.json()["error"]["fields"] == {"stake": "greater_than_equal"}
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert (detail["bet_count"], detail["pot"], detail["my_bet"]) == (0, 0, None)
    assert await balance(cami.client, org_id) == 100

    one = await place(cami.client, org_id, prono["id"], option_id=nice, stake=1)
    assert one.status_code == 201, one.text
    assert one.json()["stake"] == 1
    assert await balance(cami.client, org_id) == 99
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert (detail["bet_count"], detail["pot"]) == (1, 1)
    await caches_match(org.id)


async def test_without_a_laurel_left_no_bet_is_possible(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    first = await publish(hugo.client, org_id)
    second = await publish(hugo.client, org_id, question="Le pot aura-t-il lieu ?")
    all_in = await place(
        cami.client, org_id, first["id"], option_id=option(first, "Nice"), stake=100
    )
    assert all_in.status_code == 201
    assert await balance(cami.client, org_id) == 0

    nice = option(second, "Nice")
    one = await place(cami.client, org_id, second["id"], option_id=nice, stake=1)
    assert one.status_code == 409 and one.json()["error"]["code"] == "insufficient_balance"
    free = await place(cami.client, org_id, second["id"], option_id=nice, stake=0)
    assert free.status_code == 422 and free.json()["error"]["fields"] == {"stake": "too_low"}


async def test_the_shares_are_those_of_the_laurels_staked(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, org_id, options=["Nice", "Monaco"])

    # Nothing staked yet: 0 % everywhere.
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert shares(detail) == [("Nice", 0, 0, 0), ("Monaco", 0, 0, 0)]

    await place(cami.client, org_id, prono["id"], option_id=option(prono, "Nice"), stake=30)
    await place(leo.client, org_id, prono["id"], option_id=option(prono, "Monaco"), stake=10)
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    # One person on each side, but three laurels out of four on Nice.
    assert shares(detail) == [("Nice", 1, 30, 75), ("Monaco", 1, 10, 25)]
    # La une's gauge draws the same split.
    page = (await cami.client.get(f"/api/orgs/{org.id}/front-page")).json()
    assert page["headline"]["id"] == prono["id"]
    assert shares(page["headline"]) == shares(detail)


async def test_few_people_staking_much_outweigh_many_staking_little(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    others = [await person(org, "reader", name) for name in ("Léo", "Manon", "Zoé")]
    prono = await publish(hugo.client, org_id, options=["Nice", "Monaco"])

    await place(cami.client, org_id, prono["id"], option_id=option(prono, "Nice"), stake=60)
    for who, stake in zip(others, (10, 10, 20), strict=True):
        await place(who.client, org_id, prono["id"], option_id=option(prono, "Monaco"), stake=stake)
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert shares(detail) == [("Nice", 1, 60, 60), ("Monaco", 3, 40, 40)]


async def test_number_and_date_ranges_share_the_laurels(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")
    goals = await publish(hugo.client, org_id, kind="number", options=[], number_unit="buts")
    await place(cami.client, org_id, goals["id"], number_value="3", stake=30)
    await place(leo.client, org_id, goals["id"], number_value="5", stake=5)
    await place(manon.client, org_id, goals["id"], number_value="5", stake=5)
    detail = (await cami.client.get(url(org.id, goals["id"]))).json()
    assert detail["distribution"] == [
        {"label": "3", "count": 1, "stake_total": 30, "share_pct": 75},
        {"label": "5", "count": 2, "stake_total": 10, "share_pct": 25},
    ]

    day = await publish(hugo.client, org_id, kind="date", options=[])
    soon = (clock.now() + timedelta(days=2)).date().isoformat()
    later = (clock.now() + timedelta(days=9)).date().isoformat()
    await place(cami.client, org_id, day["id"], date_value=soon, stake=1)
    await place(leo.client, org_id, day["id"], date_value=soon, stake=1)
    await place(manon.client, org_id, day["id"], date_value=later, stake=8)
    detail = (await cami.client.get(url(org.id, day["id"]))).json()
    assert [(b["label"], b["count"], b["share_pct"]) for b in detail["distribution"]] == [
        (soon, 2, 20),
        (later, 1, 80),
    ]


async def test_bets_placed_without_a_stake_before_the_rule_stay_as_they_were(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")
    prono = await publish(hugo.client, org_id, options=["Nice", "Monaco"])
    old = await old_bet_without_stake(prono["id"], cami.member, option_id=option(prono, "Nice"))

    # Its person counts, its laurels do not: nobody staked anything yet.
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert shares(detail) == [("Nice", 1, 0, 0), ("Monaco", 0, 0, 0)]
    assert (detail["my_bet"]["stake"], detail["bet_count"], detail["pot"]) == (0, 1, 0)

    # The new bets that follow stake laurels; the old one stays first.
    for who, answer, stake in ((leo, "Nice", 10), (manon, "Monaco", 30)):
        placed = await place(
            who.client, org_id, prono["id"], option_id=option(prono, answer), stake=stake
        )
        assert placed.status_code == 201, placed.text
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert [(b["member"]["pseudo"], b["stake"], b["rank"]) for b in detail["bets"]] == [
        ("Cami", 0, 1),
        ("Léo", 10, 2),
        ("Manon", 30, 3),
    ]
    assert shares(detail) == [("Nice", 2, 10, 25), ("Monaco", 1, 30, 75)]

    # Settled as before: Cami's bet wins the base gain but no share of the pot, which goes to
    # Léo, the winner who staked.
    await close(fake_clock)
    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert [(b["stake"], b["outcome"], b["payout"]) for b in detail["bets"]] == [
        (0, "won", 20),
        (10, "won", 60),
        (30, "lost", 0),
    ]
    assert await balance(cami.client, org_id) == 120
    await caches_match(org.id)
    async with transaction() as session:
        stored = await session.get(Bet, old)
        assert stored is not None and stored.stake == 0


async def test_an_open_ended_date_bet_again_stakes_at_least_one_laurel(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    org_id = str(org.id)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(
        hugo.client, org_id, kind="date", options=[], open_ended=True, closes_at=None
    )
    tomorrow = (clock.now() + timedelta(days=1)).date()
    old = await old_bet_without_stake(prono["id"], cami.member, date_value=tomorrow)

    # Cami's old date has passed: a new one stakes at least one laurel too.
    fake_clock.advance(timedelta(days=2))
    assert (await cami.client.get(url(org.id, prono["id"]))).json()["can_rebet"] is True
    later = (clock.now() + timedelta(days=3)).date().isoformat()
    free = await place(cami.client, org_id, prono["id"], date_value=later, stake=0)
    assert free.status_code == 422 and free.json()["error"]["fields"] == {"stake": "too_low"}
    again = await place(cami.client, org_id, prono["id"], date_value=later, stake=1)
    assert again.status_code == 201, again.text

    detail = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert [(b["stake"], b["superseded"]) for b in detail["bets"]] == [(0, True), (1, False)]
    assert detail["pot"] == 1
    assert detail["distribution"] == [
        {"label": later, "count": 1, "stake_total": 1, "share_pct": 100}
    ]
    assert await balance(cami.client, org_id) == 99
    await caches_match(org.id)
    async with transaction() as session:
        stored = await session.get(Bet, old)
        assert stored is not None and stored.stake == 0
