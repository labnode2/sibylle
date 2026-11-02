from datetime import timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from tests.conftest import MakeOrg, MakePerson, Person
from tests.contract.test_pronos import balance, place, publish

from sibylle import clock
from sibylle.db.models import Membership
from sibylle.db.session import transaction
from sibylle.services.ledger import check_caches
from sibylle.worker.jobs import advance_pronos

pytestmark = pytest.mark.contract


def url(org_id: object, prono_id: str, action: str = "") -> str:
    base = f"/api/orgs/{org_id}/pronos/{prono_id}"
    return f"{base}/{action}" if action else base


async def score(client: httpx.AsyncClient, org_id: object) -> int:
    value: int = (await client.get(f"/api/orgs/{org_id}")).json()["my_membership"]["season_score"]
    return value


async def close(fake_clock: clock.FakeClock) -> None:
    """Moves past every closing time and lets the worker close the pronos."""
    fake_clock.advance(timedelta(days=4))
    await advance_pronos()


def option(prono: dict[str, Any], label: str) -> str:
    return str(next(o["id"] for o in prono["options"] if o["label"] == label))


async def caches_match(org_id: object) -> None:
    async with transaction() as session:
        assert await check_caches(session, org_id) == []  # type: ignore[arg-type]


async def test_four_stakes_of_ten_and_one_winner(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    """The spec's example: the winner gets the base gain plus the whole pot of 40."""
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    winner = await person(org, "reader", "Cami")
    losers = [await person(org, "reader", name) for name in ("Léo", "Manon", "Zoé")]
    prono = await publish(hugo.client, str(org.id))
    await place(winner.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    for loser in losers:
        await place(
            loser.client, str(org.id), prono["id"], option_id=option(prono, "Monaco"), stake=10
        )
    await close(fake_clock)

    response = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["state"] == "resolved"
    assert {o["label"]: o["is_correct"] for o in detail["options"]} == {
        "Nice": True,
        "Nul": False,
        "Monaco": False,
    }
    edition = detail["special_edition"]
    assert (edition["kind"], edition["settlement_seq"], edition["result"]) == (
        "resolution",
        1,
        "Nice",
    )
    assert (edition["pot"], edition["pot_lost"]) == (40, False)
    [won] = edition["winners"]
    assert won["member"]["pseudo"] == "Cami"
    assert (won["base_gain"], won["early_bird"], won["pot_share"], won["payout"]) == (20, 0, 40, 60)
    assert [(b["outcome"], b["payout"]) for b in detail["bets"]] == [
        ("won", 60),
        ("lost", 0),
        ("lost", 0),
        ("lost", 0),
    ]
    assert [e["kind"] for e in detail["events"]][-2:] == ["closed", "resolved"]

    assert (await balance(winner.client, str(org.id)), await score(winner.client, org.id)) == (
        150,
        50,
    )
    for loser in losers:
        assert (await balance(loser.client, str(org.id)), await score(loser.client, org.id)) == (
            90,
            -10,
        )
    await caches_match(org.id)


async def test_the_early_bird_bonus(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=20, early_bird_count=2)
    hugo = await person(org, "journalist")
    players = [await person(org) for _ in range(3)]
    prono = await publish(hugo.client, str(org.id), kind="yes_no", options=[])
    for player in players:
        await place(
            player.client, str(org.id), prono["id"], option_id=option(prono, "Oui"), stake=0
        )
    await close(fake_clock)

    detail = (
        await hugo.client.post(
            url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Oui")]}
        )
    ).json()
    edition = detail["special_edition"]
    assert [w["early_bird"] for w in edition["winners"]] == [4, 4, 0]
    assert [w["payout"] for w in edition["winners"]] == [24, 24, 20]
    # Nobody staked: there was no pot to lose.
    assert edition["pot_lost"] is False


async def test_the_pot_is_lost_without_winners(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org)
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=30)
    await close(fake_clock)
    edition = (
        await hugo.client.post(
            url(org.id, prono["id"], "resolve"),
            json={"correct_option_ids": [option(prono, "Nice")]},
        )
    ).json()["special_edition"]
    assert (edition["winners"], edition["pot_lost"]) == ([], True)
    assert (await balance(cami.client, str(org.id)), await score(cami.client, org.id)) == (70, -30)


async def test_the_closest_number_wins(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist")
    a, b, c = [await person(org, pseudo=name) for name in ("Ana", "Bob", "Cyd")]
    prono = await publish(hugo.client, str(org.id), kind="number", options=[], number_unit="buts")
    for player, value in ((a, "2"), (b, "3"), (c, "5")):
        await place(player.client, str(org.id), prono["id"], number_value=value, stake=10)
    await close(fake_clock)

    missing = await hugo.client.post(url(org.id, prono["id"], "resolve"), json={})
    assert missing.json()["error"]["fields"] == {"result_number": "missing"}
    edition = (
        await hugo.client.post(url(org.id, prono["id"], "resolve"), json={"result_number": "2.5"})
    ).json()["special_edition"]
    assert edition["result"] == "2,5 buts"
    assert {w["member"]["pseudo"]: w["pot_share"] for w in edition["winners"]} == {
        "Ana": 15,
        "Bob": 15,
    }


async def test_an_open_ended_date_is_resolved_while_open(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org)
    prono = await publish(
        hugo.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    day = (clock.now() + timedelta(days=5)).date().isoformat()
    await place(cami.client, str(org.id), prono["id"], date_value=day, stake=0)
    detail = (
        await hugo.client.post(url(org.id, prono["id"], "resolve"), json={"result_date": day})
    ).json()
    assert detail["state"] == "resolved"
    assert detail["special_edition"]["winners"][0]["member"]["id"] == str(cami.member.id)


async def test_who_may_resolve_and_when(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org)
    prono = await publish(hugo.client, str(org.id))
    nice = {"correct_option_ids": [option(prono, "Nice")]}
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=0)
    empty = await publish(hugo.client, str(org.id))

    too_early = await hugo.client.post(url(org.id, prono["id"], "resolve"), json=nice)
    assert (too_early.status_code, too_early.json()["error"]["code"]) == (409, "invalid_state")
    await close(fake_clock)
    reader = await cami.client.post(url(org.id, prono["id"], "resolve"), json=nice)
    assert reader.status_code == 403
    unknown = await hugo.client.post(
        url(org.id, prono["id"], "resolve"),
        json={"correct_option_ids": [empty["options"][0]["id"]]},
    )
    assert unknown.json()["error"]["fields"] == {"correct_option_ids": "unknown"}
    none = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": []}
    )
    assert none.json()["error"]["fields"] == {"correct_option_ids": "missing"}
    # A prono nobody bet on is relaunched or cancelled, never resolved.
    nobody = await hugo.client.post(
        url(org.id, empty["id"], "resolve"),
        json={"correct_option_ids": [option(empty, "Nice")]},
    )
    assert nobody.status_code == 409

    assert (await hugo.client.post(url(org.id, prono["id"], "resolve"), json=nice)).is_success
    again = await hugo.client.post(url(org.id, prono["id"], "resolve"), json=nice)
    assert again.status_code == 409


async def test_relaunching_a_postponed_prono(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org)
    leo = await person(org)
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    open_now = await hugo.client.post(
        url(org.id, prono["id"], "relaunch"),
        json={"closes_at": (clock.now() + timedelta(days=5)).isoformat()},
    )
    assert open_now.status_code == 409
    await close(fake_clock)

    past = await hugo.client.post(
        url(org.id, prono["id"], "relaunch"),
        json={"closes_at": (clock.now() - timedelta(hours=1)).isoformat()},
    )
    assert past.json()["error"]["fields"] == {"closes_at": "in_past"}
    reader = await cami.client.post(
        url(org.id, prono["id"], "relaunch"),
        json={"closes_at": (clock.now() + timedelta(days=2)).isoformat()},
    )
    assert reader.status_code == 403
    new_closing = clock.now() + timedelta(days=2)
    detail = (
        await hugo.client.post(
            url(org.id, prono["id"], "relaunch"),
            json={"closes_at": new_closing.isoformat(), "reason": "Match reporté"},
        )
    ).json()
    assert (detail["state"], detail["relaunch_count"], detail["pot"]) == ("open", 1, 10)
    assert [(b["rank"], b["stake"]) for b in detail["bets"]] == [(1, 10)]
    assert detail["events"][-1]["kind"] == "relaunched"
    assert detail["events"][-1]["data"]["reason"] == "Match reporté"

    late = await place(
        leo.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=5
    )
    assert late.status_code == 201 and late.json()["rank"] == 2


async def test_correcting_then_cancelling(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor")
    hugo = await person(org, "journalist")
    nice_fan = await person(org, pseudo="Cami")
    draw_fans = [await person(org, pseudo=name) for name in ("Léo", "Zoé")]
    prono = await publish(hugo.client, str(org.id))
    await place(
        nice_fan.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=20
    )
    for fan in draw_fans:
        await place(fan.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=10)
    await close(fake_clock)
    nice = {"correct_option_ids": [option(prono, "Nice")]}
    draw = {"correct_option_ids": [option(prono, "Nul")]}
    await hugo.client.post(url(org.id, prono["id"], "resolve"), json=nice)
    assert await balance(nice_fan.client, str(org.id)) == 80 + 20 + 40

    journalist = await hugo.client.post(url(org.id, prono["id"], "correct"), json=draw)
    assert journalist.status_code == 403
    unchanged = await ines.client.post(url(org.id, prono["id"], "correct"), json=nice)
    assert unchanged.json()["error"]["fields"] == {"result": "unchanged"}

    corrected = (await ines.client.post(url(org.id, prono["id"], "correct"), json=draw)).json()
    edition = corrected["special_edition"]
    assert (edition["kind"], edition["settlement_seq"], edition["result"]) == (
        "correction",
        2,
        "Nul",
    )
    assert sum(w["pot_share"] for w in edition["winners"]) == 40
    assert await balance(nice_fan.client, str(org.id)) == 80
    assert await score(nice_fan.client, org.id) == -20
    for fan in draw_fans:
        assert await balance(fan.client, str(org.id)) == 90 + 20 + 20
        assert await score(fan.client, org.id) == 20 + 10

    # Correcting back gives the first result again.
    back = (await ines.client.post(url(org.id, prono["id"], "correct"), json=nice)).json()
    assert back["special_edition"]["settlement_seq"] == 3
    assert await balance(nice_fan.client, str(org.id)) == 140
    assert await balance(draw_fans[0].client, str(org.id)) == 90

    by_journalist = await hugo.client.post(url(org.id, prono["id"], "cancel"), json={})
    assert by_journalist.status_code == 403
    cancelled = (
        await ines.client.post(url(org.id, prono["id"], "cancel"), json={"reason": "Doublon"})
    ).json()
    assert cancelled["state"] == "cancelled"
    assert cancelled["special_edition"]["kind"] == "cancellation"
    assert cancelled["special_edition"]["winners"] == []
    assert {b["outcome"] for b in cancelled["bets"]} == {"refunded"}
    for player in (nice_fan, *draw_fans):
        assert (await balance(player.client, str(org.id)), await score(player.client, org.id)) == (
            100,
            0,
        )
    await caches_match(org.id)


async def test_cancelling_an_open_prono_gives_stakes_back(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor")
    cami = await person(org)
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=35)
    detail = (await ines.client.post(url(org.id, prono["id"], "cancel"), json={})).json()
    assert detail["state"] == "cancelled"
    assert await balance(cami.client, str(org.id)) == 100
    late = await place(
        cami.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=0
    )
    assert late.status_code == 409


async def test_a_correction_can_leave_a_negative_balance(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor")
    cami = await person(org)
    leo = await person(org)
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await place(leo.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=10)
    await close(fake_clock)
    await ines.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert await balance(cami.client, str(org.id)) == 130

    # Cami spends everything on another prono, then the result is corrected.
    other = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), other["id"], option_id=option(other, "Nice"), stake=130)
    await ines.client.post(
        url(org.id, prono["id"], "correct"), json={"correct_option_ids": [option(prono, "Nul")]}
    )
    assert await balance(cami.client, str(org.id)) == -40

    third = await publish(ines.client, str(org.id))
    refused = await place(
        cami.client, str(org.id), third["id"], option_id=option(third, "Nice"), stake=10
    )
    assert refused.json()["error"]["code"] == "insufficient_balance"
    free = await place(
        cami.client, str(org.id), third["id"], option_id=option(third, "Nice"), stake=0
    )
    assert free.status_code == 201


async def test_a_member_who_left_is_paid(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist")
    gone = await person(org)
    prono = await publish(hugo.client, str(org.id))
    await place(gone.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    async with transaction() as session:
        member = await session.get(Membership, gone.member.id)
        assert member is not None
        member.status = "left"
    await close(fake_clock)
    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200
    async with transaction() as session:
        member = await session.get(Membership, gone.member.id)
        assert member is not None and member.balance == 90 + 20 + 10


async def test_reports(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org)
    prono = await publish(hugo.client, str(org.id))
    created = await cami.client.post(
        url(org.id, prono["id"], "reports"),
        json={"kind": "result_error", "message": "  Le match a fini 2-2.  "},
    )
    assert created.status_code == 201
    report = created.json()
    assert (report["kind"], report["state"], report["message"]) == (
        "result_error",
        "open",
        "Le match a fini 2-2.",
    )
    no_message = await cami.client.post(
        url(org.id, prono["id"], "reports"), json={"kind": "content"}
    )
    assert no_message.status_code == 201 and no_message.json()["message"] is None
    too_long = await cami.client.post(
        url(org.id, prono["id"], "reports"), json={"kind": "content", "message": "x" * 501}
    )
    assert too_long.status_code == 422
    unknown = await cami.client.post(url(org.id, prono["id"], "reports"), json={"kind": "spam"})
    assert unknown.status_code == 422


async def test_outsiders_get_404(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    other = await make_org("Autre rédaction")
    hugo = await person(org, "journalist")
    cami = await person(org)
    stranger: Person = await person(other, "editor")
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=0)
    await close(fake_clock)
    later = (clock.now() + timedelta(days=1)).isoformat()
    calls = {
        "resolve": {"correct_option_ids": [option(prono, "Nice")]},
        "correct": {"result_number": str(Decimal("1"))},
        "relaunch": {"closes_at": later},
        "cancel": {},
        "reports": {"kind": "content"},
    }
    for action, body in calls.items():
        for org_id in (org.id, other.id):
            response = await stranger.client.post(url(org_id, prono["id"], action), json=body)
            assert response.status_code == 404, (action, org_id, response.text)
