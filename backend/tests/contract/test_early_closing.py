"""Closing a prono's bets before their planned time (« Clore les paris maintenant »), then giving
its result at once, without waiting for the expected result date."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import notifications
from tests.contract.test_pronos import balance, place, publish
from tests.contract.test_results import caches_match, close, option, url

from sibylle import clock
from sibylle.worker.jobs import advance_pronos, designation_reminders

pytestmark = pytest.mark.contract


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def test_the_newsroom_closes_the_bets_before_their_time(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, pseudo="Cami")
    leo = await person(org, pseudo="Léo")
    planned = clock.now() + timedelta(days=3)
    expected = clock.now() + timedelta(days=4)
    prono = await publish(
        hugo.client,
        str(org.id),
        closes_at=planned.isoformat(),
        result_expected_at=expected.isoformat(),
    )
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)

    before = clock.now()
    response = await hugo.client.post(url(org.id, prono["id"], "close"))
    after = clock.now()
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["state"] == "closed"
    # The closing is the moment of the closure; the expected result date stays as it was.
    closed_at = instant(detail["closes_at"])
    assert before <= closed_at <= after
    assert instant(detail["result_expected_at"]) == expected
    # The bets and the pot stay as they were.
    assert (detail["bet_count"], detail["pot"]) == (1, 10)
    # The history keeps who closed it and the closing planned until then.
    event = detail["events"][-1]
    assert (event["kind"], event["by"]["pseudo"]) == ("closed", "Hugo")
    assert instant(event["data"]["previous_closes_at"]) == planned
    assert instant(event["data"]["closes_at"]) == closed_at

    # The bets stop at once, for everyone.
    late = await place(
        leo.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=5
    )
    assert (late.status_code, late.json()["error"]["code"]) == (409, "invalid_state")
    seen = (await leo.client.get(url(org.id, prono["id"]))).json()
    assert (seen["state"], seen["closes_at"]) == ("closed", detail["closes_at"])
    assert await balance(leo.client, str(org.id)) == 100

    # The planned closing passes: the worker has nothing left to close.
    fake_clock.advance(timedelta(days=3, minutes=1))
    assert await advance_pronos() == 0
    again = (await hugo.client.get(url(org.id, prono["id"]))).json()
    assert [e["kind"] for e in again["events"]].count("closed") == 1
    assert again["closes_at"] == detail["closes_at"]


async def test_the_result_comes_before_the_expected_date(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, pseudo="Cami")
    leo = await person(org, pseudo="Léo")
    expected = clock.now() + timedelta(days=4)
    prono = await publish(hugo.client, str(org.id), result_expected_at=expected.isoformat())
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await place(leo.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=10)
    assert (await hugo.client.post(url(org.id, prono["id"], "close"))).is_success

    # Straight away on la une, among the results to designate.
    front = (await hugo.client.get(f"/api/orgs/{org.id}/front-page")).json()
    assert [p["id"] for p in front["to_designate"]] == [prono["id"]]

    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    assert clock.now() < expected
    detail = resolved.json()
    assert detail["state"] == "resolved"
    assert [e["kind"] for e in detail["events"]][-2:] == ["closed", "resolved"]
    [winner] = detail["special_edition"]["winners"]
    assert (winner["member"]["pseudo"], winner["payout"]) == ("Cami", 20 + 20)
    assert await balance(cami.client, str(org.id)) == 90 + 40
    assert await balance(leo.client, str(org.id)) == 90
    await caches_match(org.id)

    # Already resolved: no reminder to designate it once the expected date comes.
    fake_clock.set(expected + timedelta(minutes=1))
    assert await advance_pronos() == 0
    assert await designation_reminders() == 0
    fake_clock.advance(timedelta(days=8))
    assert await designation_reminders() == 0
    assert await notifications("designation_reminder") == []


async def test_a_closing_already_passed_stays(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    """The planned closing passed a few seconds ago and the worker has not got to it yet: the
    bets stopped then, so the closing stays where it was."""
    org = await make_org()
    hugo = await person(org, "journalist")
    planned = clock.now() + timedelta(hours=1)
    prono = await publish(hugo.client, str(org.id), closes_at=planned.isoformat())
    fake_clock.set(planned + timedelta(seconds=20))

    detail = (await hugo.client.post(url(org.id, prono["id"], "close"))).json()
    assert detail["state"] == "closed"
    assert instant(detail["closes_at"]) == planned
    assert await advance_pronos() == 0


async def test_who_may_close_the_bets_and_when(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, pseudo="Cami")
    prono = await publish(hugo.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=1)

    def refused(response: Any) -> tuple[int, str]:
        return response.status_code, response.json()["error"]["code"]

    # The same rights as a relaunch: not the readers.
    reader = await cami.client.post(url(org.id, prono["id"], "close"))
    assert refused(reader) == (403, "forbidden")
    assert (await cami.client.get(url(org.id, prono["id"]))).json()["state"] == "open"

    # The editor may too, even without a bet; such a prono is then relaunched or cancelled.
    empty = await publish(hugo.client, str(org.id))
    closed = await ines.client.post(url(org.id, empty["id"], "close"))
    assert closed.status_code == 200 and closed.json()["state"] == "closed"
    relaunched = await hugo.client.post(
        url(org.id, empty["id"], "relaunch"),
        json={"closes_at": (clock.now() + timedelta(days=1)).isoformat()},
    )
    assert relaunched.json()["state"] == "open"

    # Only an open prono with a closing: never twice, nor a resolved or cancelled one…
    assert (await hugo.client.post(url(org.id, prono["id"], "close"))).is_success
    assert refused(await hugo.client.post(url(org.id, prono["id"], "close"))) == (
        409,
        "invalid_state",
    )
    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.json()["state"] == "resolved"
    assert refused(await hugo.client.post(url(org.id, prono["id"], "close")))[0] == 409
    cancelled = await ines.client.post(url(org.id, empty["id"], "cancel"), json={})
    assert cancelled.json()["state"] == "cancelled"
    assert refused(await ines.client.post(url(org.id, empty["id"], "close")))[0] == 409

    # …nor an open-ended date, which has no closing, a scheduled prono or a proposal.
    open_ended = await publish(
        hugo.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    scheduled = await publish(
        hugo.client, str(org.id), opens_at=(clock.now() + timedelta(hours=2)).isoformat()
    )
    proposal = await publish(cami.client, str(org.id))
    for waiting in (open_ended, scheduled, proposal):
        response = await hugo.client.post(url(org.id, waiting["id"], "close"))
        assert refused(response) == (409, "invalid_state"), waiting["state"]
        assert (await hugo.client.get(url(org.id, waiting["id"]))).json()["state"] == waiting[
            "state"
        ]

    # The worker's own closing still comes at the planned time.
    later = await publish(hugo.client, str(org.id))
    await close(fake_clock)
    detail = (await hugo.client.get(url(org.id, later["id"]))).json()
    assert (detail["state"], detail["events"][-1]["by"]) == ("closed", None)
