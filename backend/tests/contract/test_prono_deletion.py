"""Deleting a cancelled prono (`DELETE /orgs/{org}/pronos/{id}`): only a mark beside its state. It
leaves the lists, la une, its discussion and the bubbles, and its page answers 404; the ledger
keeps every entry, so the members' history keeps the refunds of its cancellation, and the export
keeps what it holds about it, marked deleted."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import notifications as outbox
from tests.contract.test_discussion import write
from tests.contract.test_game_schedule import record_events
from tests.contract.test_notification_list import on
from tests.contract.test_pronos import balance, place, publish
from tests.contract.test_results import caches_match, close, option, url

from sibylle import clock
from sibylle.notify.dispatch import dispatch
from sibylle.notify.email import MemorySender, Renderer

pytestmark = pytest.mark.contract


async def delete(client: httpx.AsyncClient, org_id: object, prono_id: str) -> httpx.Response:
    return await client.delete(url(org_id, prono_id))


async def listed(client: httpx.AsyncClient, org_id: object, *states: str) -> list[str]:
    response = await client.get(f"/api/orgs/{org_id}/pronos", params={"state": list(states)})
    assert response.status_code == 200, response.text
    return [prono["id"] for prono in response.json()["items"]]


async def history(client: httpx.AsyncClient, org_id: object) -> list[dict[str, Any]]:
    response = await client.get(f"/api/orgs/{org_id}/members/me/ledger")
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def test_a_cancelled_prono_is_deleted(
    make_org: MakeOrg, person: MakePerson, monkeypatch: pytest.MonkeyPatch
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    kept = await publish(hugo.client, str(org.id), question="Le pot aura-t-il lieu ?")
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=30)
    await place(cami.client, str(org.id), kept["id"], option_id=option(kept, "Nul"), stake=10)
    await write(cami.client, org.id, prono["id"], "Allez Nice !")
    reported = await cami.client.post(url(org.id, prono["id"], "reports"), json={"kind": "content"})
    assert reported.status_code == 201, reported.text
    still_open = await delete(ines.client, org.id, prono["id"])
    assert still_open.status_code == 409 and still_open.json()["error"]["code"] == "invalid_state"
    cancelled = await ines.client.post(url(org.id, prono["id"], "cancel"), json={})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["can_delete"] is True
    before = await history(cami.client, org.id)
    assert await balance(cami.client, str(org.id)) == 90
    # The result of the cancellation waits for Cami in the bubbles, next to the open prono.
    assert await on(cami, org.id) == {prono["id"]: ("cancelled", 1), kept["id"]: ("open", 1)}

    events = record_events(monkeypatch)
    deleted = await delete(ines.client, org.id, prono["id"])
    assert deleted.status_code == 204, deleted.text
    # The screens on the prono or the newsroom reload; so do the bubbles of those notified.
    assert ("prono.deleted", {"prono_id": prono["id"]}) in events
    assert ("notification.changed", {"org_id": str(org.id)}) in events

    # Its page answers 404 to everyone, and so does everything that hangs from it.
    for who in (ines, hugo, cami):
        assert (await who.client.get(url(org.id, prono["id"]))).status_code == 404
    hanging = [
        await cami.client.get(url(org.id, prono["id"], "messages")),
        await cami.client.post(url(org.id, prono["id"], "messages"), json={"body": "Encore ?"}),
        await cami.client.put(url(org.id, prono["id"], "reactions/yes")),
        await cami.client.post(url(org.id, prono["id"], "reports"), json={"kind": "content"}),
        await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nul"), stake=1),
        await ines.client.post(url(org.id, prono["id"], "cancel"), json={}),
        await delete(ines.client, org.id, prono["id"]),
    ]
    assert [response.status_code for response in hanging] == [404] * len(hanging)

    # Gone from the lists, la une and the bubbles; the other prono stays.
    for who in (ines, cami):
        assert await listed(who.client, org.id) == [kept["id"]]
        assert await listed(who.client, org.id, "resolved", "cancelled") == []
    front = await cami.client.get(f"/api/orgs/{org.id}/front-page")
    assert front.json()["headline"]["id"] == kept["id"] and prono["id"] not in front.text
    assert await on(cami, org.id) == {kept["id"]: ("open", 1)}

    # The ledger keeps every entry: the same history, the refund included, and the same balance.
    after = await history(cami.client, org.id)
    assert after == [
        {**entry, "prono": entry["prono"] and {**entry["prono"], "deleted": True}}
        if entry["prono"] and entry["prono"]["id"] == prono["id"]
        else entry
        for entry in before
    ]
    assert [e["kind"] for e in after if e["prono"] and e["prono"]["id"] == prono["id"]] == [
        "refund",
        "stake",
    ]
    assert await balance(cami.client, str(org.id)) == 90
    await caches_match(org.id)

    # The editor still handles its open report, which no longer links to it.
    [report] = (await ines.client.get(f"/api/orgs/{org.id}/reports")).json()
    assert report["prono"] == {"id": prono["id"], "question": prono["question"], "deleted": True}

    # The export keeps what it holds about the prono, marked deleted, as it keeps a replaced bet.
    export = (await cami.client.get("/api/me/export")).json()
    [newsroom] = export["newsrooms"]
    marked = {bet["question"]: bet["prono_deleted_at"] is not None for bet in newsroom["bets"]}
    assert marked == {prono["question"]: True, kept["question"]: False}
    assert [(e["kind"], e["prono_deleted_at"] is not None) for e in newsroom["laurels"]] == [
        ("starting_balance", False),
        ("stake", True),
        ("stake", False),
        ("refund", True),
    ]
    assert [m["prono_deleted_at"] is not None for m in newsroom["messages"]] == [True]
    assert [r["prono_deleted_at"] is not None for r in newsroom["reports"]] == [True]


async def test_its_notifications_left_unsent_are_skipped(
    make_org: MakeOrg, person: MakePerson
) -> None:
    """The result of a cancellation that has not left yet: its prono is gone, nothing to tell."""
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    prono = await publish(ines.client, str(org.id))
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await ines.client.post(url(org.id, prono["id"], "cancel"), json={})
    assert (await delete(ines.client, org.id, prono["id"])).status_code == 204

    sender = MemorySender()
    await dispatch(sender, Renderer())
    assert [n.state for n in await outbox("result")] == ["skipped"]
    assert sender.sent == []


async def test_only_a_cancelled_prono_is_deleted(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    resolved = await publish(ines.client, str(org.id))
    closed = await publish(ines.client, str(org.id), question="Il neigera à Noël ?")
    await place(
        cami.client, str(org.id), resolved["id"], option_id=option(resolved, "Nice"), stake=1
    )
    await close(fake_clock)
    designated = await ines.client.post(
        url(org.id, resolved["id"], "resolve"),
        json={"correct_option_ids": [option(resolved, "Nice")]},
    )
    assert designated.status_code == 200, designated.text
    scheduled = await publish(
        ines.client, str(org.id), opens_at=(clock.now() + timedelta(hours=2)).isoformat()
    )
    opened = await publish(ines.client, str(org.id))
    proposed = await publish(cami.client, str(org.id), question="Une idée de Cami ?")
    rejected = await publish(cami.client, str(org.id), question="Une autre idée ?")
    await ines.client.post(url(org.id, rejected["id"], "reject"), json={})
    pronos = {
        "resolved": resolved,
        "closed": closed,
        "scheduled": scheduled,
        "open": opened,
        "proposed": proposed,
        "rejected": rejected,
    }

    for state, prono in pronos.items():
        detail = (await ines.client.get(url(org.id, prono["id"]))).json()
        assert (detail["state"], detail["can_delete"]) == (state, False)
        refused = await delete(ines.client, org.id, prono["id"])
        assert refused.status_code == 409, (state, refused.text)
        assert refused.json()["error"]["code"] == "invalid_state"
        assert (await ines.client.get(url(org.id, prono["id"]))).status_code == 200


async def test_who_may_delete(make_org: MakeOrg, person: MakePerson) -> None:
    """The same rights as cancelling: the editor; a newsroom's outsider does not even see it."""
    org = await make_org()
    other = await make_org("Autre rédaction")
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    stranger = await person(other, "editor", "Inconnu")
    prono = await publish(hugo.client, str(org.id))
    await ines.client.post(url(org.id, prono["id"], "cancel"), json={})

    for who in (hugo, cami):
        assert (await who.client.get(url(org.id, prono["id"]))).json()["can_delete"] is False
        refused = await delete(who.client, org.id, prono["id"])
        assert refused.status_code == 403, refused.text
    for org_id in (org.id, other.id):
        assert (await delete(stranger.client, org_id, prono["id"])).status_code == 404
    assert (await delete(ines.client, org.id, prono["id"])).status_code == 204
