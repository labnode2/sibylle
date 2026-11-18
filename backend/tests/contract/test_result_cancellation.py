"""Cancelling only the result of a prono (« Annuler le résultat »): the payouts are taken back,
the stakes stay in play and the prono waits for a new result, or its cancellation."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from tests.conftest import MakeOrg, MakePerson, Person
from tests.contract.test_pronos import balance, place, publish
from tests.contract.test_results import caches_match, close, option, score, url

from sibylle import clock
from sibylle.db.models import Prono, Settlement
from sibylle.db.session import transaction

pytestmark = pytest.mark.contract


async def standing(people: list[Person], org_id: object) -> list[tuple[int, int]]:
    """Each one's balance and season score."""
    return [(await balance(p.client, str(org_id)), await score(p.client, org_id)) for p in people]


async def settlements(prono_id: str) -> list[tuple[int, str, int | None]]:
    """The prono's settlements in order: seq, kind, and the seq of the one that reversed it."""
    async with transaction() as session:
        rows = (
            await session.scalars(
                select(Settlement)
                .where(Settlement.prono_id == uuid.UUID(prono_id))
                .order_by(Settlement.seq)
            )
        ).all()
        seqs = {s.id: s.seq for s in rows}
        return [
            (s.seq, s.kind, seqs.get(s.reversed_by_id) if s.reversed_by_id else None) for s in rows
        ]


async def a_resolved_prono(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> tuple[Any, Person, Person, list[Person], dict[str, Any]]:
    """Cami stakes 20 on Nice, Léo and Zoé 10 each on the draw; Hugo designates Nice."""
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    players = [await person(org, pseudo=name) for name in ("Cami", "Léo", "Zoé")]
    prono = await publish(hugo.client, str(org.id))
    await place(
        players[0].client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=20
    )
    for fan in players[1:]:
        await place(fan.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=10)
    await close(fake_clock)
    assert await standing(players, org.id) == [(80, 0), (90, 0), (90, 0)]
    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    # Cami takes the base gain and the whole pot; the draw fans lose their stakes.
    assert await standing(players, org.id) == [(140, 40), (90, -10), (90, -10)]
    return org, ines, hugo, players, prono


async def test_the_result_is_taken_back_and_the_stakes_stay(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org, ines, hugo, players, prono = await a_resolved_prono(make_org, person, fake_clock)

    response = await ines.client.post(
        url(org.id, prono["id"], "cancel-result"), json={"reason": "  Score mal saisi  "}
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    # Waiting for a result again, as before the designation.
    assert detail["state"] == "closed"
    assert detail["special_edition"] is None
    assert {o["label"]: o["is_correct"] for o in detail["options"]} == {
        "Nice": None,
        "Nul": None,
        "Monaco": None,
    }
    assert (detail["bet_count"], detail["pot"]) == (3, 40)
    assert [(b["stake"], b["outcome"], b["payout"]) for b in detail["bets"]] == [
        (20, "pending", 0),
        (10, "pending", 0),
        (10, "pending", 0),
    ]
    event = detail["events"][-1]
    assert (event["kind"], event["by"]["pseudo"]) == ("result_cancelled", "Inès")
    assert event["data"]["reason"] == "Score mal saisi"
    assert event["data"]["previous"] == {"correct_option_ids": [option(prono, "Nice")]}

    # The balances and scores are back to what they were before the resolution: stakes kept.
    assert await standing(players, org.id) == [(80, 0), (90, 0), (90, 0)]
    assert await settlements(prono["id"]) == [
        (1, "resolution", 2),
        (2, "result_cancellation", None),
    ]
    async with transaction() as session:
        stored = await session.get(Prono, uuid.UUID(prono["id"]))
        assert stored is not None
        assert (stored.resolved_at, stored.resolved_by) == (None, None)
    await caches_match(org.id)

    # The statement shows the gains taken back as a cancelled result, the stake still gone.
    ledger = (await players[0].client.get(f"/api/orgs/{org.id}/members/me/ledger")).json()
    entries = [(e["kind"], e["amount"], e["settlement_kind"]) for e in ledger["items"]]
    assert sorted(entries[:2]) == [
        ("reversal", -40, "result_cancellation"),
        ("reversal", -20, "result_cancellation"),
    ]
    assert sorted(entries[2:4]) == [
        ("base_gain", 20, "resolution"),
        ("pot_share", 40, "resolution"),
    ]
    assert entries[4:] == [("stake", -20, None), ("starting_balance", 100, None)]
    assert {e["prono"]["id"] for e in ledger["items"][:5]} == {prono["id"]}

    # Resolved again, on the draw this time: paid as if it had been the first result.
    again = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nul")]}
    )
    assert again.status_code == 200, again.text
    edition = again.json()["special_edition"]
    assert (edition["kind"], edition["settlement_seq"], edition["result"]) == (
        "resolution",
        3,
        "Nul",
    )
    assert sum(w["pot_share"] for w in edition["winners"]) == 40
    assert await standing(players, org.id) == [(80, -20), (130, 30), (130, 30)]
    total = sum(b for b, _ in await standing(players, org.id))
    assert total == 300 - 40 + 40 + 2 * 20  # the stakes back as the pot, plus two base gains
    assert await settlements(prono["id"]) == [
        (1, "resolution", 2),
        (2, "result_cancellation", None),
        (3, "resolution", None),
    ]
    await caches_match(org.id)

    # The new result can be corrected as any other, from the settlement now in force.
    back = await ines.client.post(
        url(org.id, prono["id"], "correct"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert back.json()["special_edition"]["settlement_seq"] == 4
    assert await standing(players, org.id) == [(140, 40), (90, -10), (90, -10)]
    assert (await settlements(prono["id"]))[2:] == [(3, "resolution", 4), (4, "correction", None)]
    await caches_match(org.id)


async def test_a_corrected_result_is_taken_back_too(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org, ines, _, players, prono = await a_resolved_prono(make_org, person, fake_clock)
    await ines.client.post(
        url(org.id, prono["id"], "correct"), json={"correct_option_ids": [option(prono, "Nul")]}
    )
    assert await standing(players, org.id) == [(80, -20), (130, 30), (130, 30)]

    response = await ines.client.post(url(org.id, prono["id"], "cancel-result"), json={})
    assert response.status_code == 200, response.text
    assert response.json()["events"][-1]["data"]["reason"] is None
    assert await standing(players, org.id) == [(80, 0), (90, 0), (90, 0)]
    assert await settlements(prono["id"]) == [
        (1, "resolution", 2),
        (2, "correction", 3),
        (3, "result_cancellation", None),
    ]
    await caches_match(org.id)


async def test_cancelling_the_prono_afterwards_gives_each_stake_back_once(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org, ines, _, players, prono = await a_resolved_prono(make_org, person, fake_clock)
    await ines.client.post(url(org.id, prono["id"], "cancel-result"), json={})

    cancelled = await ines.client.post(
        url(org.id, prono["id"], "cancel"), json={"reason": "Match annulé"}
    )
    assert cancelled.status_code == 200, cancelled.text
    detail = cancelled.json()
    assert detail["state"] == "cancelled"
    assert (detail["special_edition"]["kind"], detail["special_edition"]["settlement_seq"]) == (
        "cancellation",
        3,
    )
    assert {b["outcome"] for b in detail["bets"]} == {"refunded"}
    assert await standing(players, org.id) == [(100, 0), (100, 0), (100, 0)]
    # Nothing left to reverse: the cancellation only gives the stakes back.
    assert await settlements(prono["id"]) == [
        (1, "resolution", 2),
        (2, "result_cancellation", None),
        (3, "cancellation", None),
    ]
    await caches_match(org.id)


async def test_an_open_ended_date_opens_again(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor")
    cami = await person(org)
    leo = await person(org)
    prono = await publish(
        ines.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    day = (clock.now() + timedelta(days=5)).date().isoformat()
    await place(cami.client, str(org.id), prono["id"], date_value=day, stake=10)
    resolved = await ines.client.post(
        url(org.id, prono["id"], "resolve"), json={"result_date": day}
    )
    assert resolved.json()["state"] == "resolved"
    assert await balance(cami.client, str(org.id)) == 90 + 20 + 10

    detail = (await ines.client.post(url(org.id, prono["id"], "cancel-result"), json={})).json()
    assert (detail["state"], detail["closes_at"]) == ("open", None)
    assert await balance(cami.client, str(org.id)) == 90
    # Open again: the newsroom may still bet until the new result.
    later = (clock.now() + timedelta(days=8)).date().isoformat()
    bet = await place(leo.client, str(org.id), prono["id"], date_value=later, stake=5)
    assert bet.status_code == 201, bet.text
    again = await ines.client.post(url(org.id, prono["id"], "resolve"), json={"result_date": later})
    assert again.json()["special_edition"]["winners"][0]["member"]["id"] == str(leo.member.id)
    assert await balance(cami.client, str(org.id)) == 90
    assert await balance(leo.client, str(org.id)) == 95 + 20 + 15
    await caches_match(org.id)


async def test_who_may_cancel_a_result_and_when(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org, ines, hugo, players, prono = await a_resolved_prono(make_org, person, fake_clock)

    # The same rights as a correction: the editor only.
    for someone in (hugo, players[0]):
        refused = await someone.client.post(url(org.id, prono["id"], "cancel-result"), json={})
        assert (refused.status_code, refused.json()["error"]["code"]) == (403, "forbidden")
    too_long = await ines.client.post(
        url(org.id, prono["id"], "cancel-result"), json={"reason": "x" * 201}
    )
    assert too_long.status_code == 422
    assert await standing(players, org.id) == [(140, 40), (90, -10), (90, -10)]

    # Only a resolved prono has a result to cancel.
    assert (await ines.client.post(url(org.id, prono["id"], "cancel-result"), json={})).is_success
    twice = await ines.client.post(url(org.id, prono["id"], "cancel-result"), json={})
    assert (twice.status_code, twice.json()["error"]["code"]) == (409, "invalid_state")
    open_prono = await publish(hugo.client, str(org.id))
    still_open = await ines.client.post(url(org.id, open_prono["id"], "cancel-result"), json={})
    assert still_open.status_code == 409
    await ines.client.post(url(org.id, prono["id"], "cancel"), json={})
    cancelled = await ines.client.post(url(org.id, prono["id"], "cancel-result"), json={})
    assert cancelled.status_code == 409
    assert await standing(players, org.id) == [(100, 0), (100, 0), (100, 0)]
