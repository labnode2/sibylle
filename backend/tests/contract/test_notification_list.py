"""A member's notifications in a newsroom: the list, read or not, counted; and the bubbles of the
menus, per prono, that lead to them until the prono is opened."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import ORIGIN, MakeMember, MakeOrg, MakePerson, Person
from tests.contract.helpers import notifications as outbox
from tests.contract.test_discussion import write
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url
from tests.integration.test_realtime_bets import connect, next_of

from sibylle import clock
from sibylle.db.models import Notification
from sibylle.db.session import transaction
from sibylle.notify.dispatch import dispatch
from sibylle.notify.email import MemorySender, Renderer
from sibylle.services import notifications
from sibylle.worker.jobs import advance_pronos, closing_soon_alerts, designation_reminders

pytestmark = pytest.mark.contract


async def add(person: Person, key: str, *, state: str = "sent", type: str = "new_prono") -> None:
    async with transaction() as session:
        session.add(
            Notification(
                account_id=person.account.id,
                org_id=person.member.org_id,
                type=type,
                state=state,
                dedupe_key=key,
                payload={
                    "prono_id": "00000000-0000-0000-0000-000000000001",
                    "question": key,
                    "member_id": str(person.member.id),
                },
            )
        )


async def test_list_count_and_mark_read(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org)
    await add(cami, "un")
    await add(cami, "deux")
    await add(cami, "ignoré", state="skipped")
    base = f"/api/orgs/{org.id}/notifications"

    body = (await cami.client.get(base)).json()
    assert body["unread"] == 2
    assert {n["question"] for n in body["items"]} == {"un", "deux"}
    assert all(n["read_at"] is None for n in body["items"])

    first = body["items"][0]["id"]
    assert (await cami.client.post(f"{base}/{first}/read")).status_code == 204
    body = (await cami.client.get(base)).json()
    assert body["unread"] == 1
    assert [n["read_at"] is not None for n in body["items"]].count(True) == 1

    assert (await cami.client.post(f"{base}/read")).status_code == 204
    assert (await cami.client.get(base)).json()["unread"] == 0


async def test_isolated_by_newsroom_and_account(make_org: MakeOrg, person: MakePerson) -> None:
    org, other = await make_org(), await make_org("Autre")
    cami, hugo = await person(org), await person(org)
    await add(cami, "pour-cami")
    await add(hugo, "pour-hugo")

    assert (await cami.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1
    # Not a member there: 404, so the newsroom's existence stays private.
    assert (await cami.client.get(f"/api/orgs/{other.id}/notifications")).status_code == 404

    async with transaction() as session:
        theirs = await notifications.listing(session, hugo.account.id, org.id)
    response = await cami.client.post(f"/api/orgs/{org.id}/notifications/{theirs[0].id}/read")
    assert response.status_code == 404
    assert (await hugo.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1
    assert (await cami.client.post(f"/api/orgs/{org.id}/notifications/read")).status_code == 204
    assert (await hugo.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1


async def test_second_newsroom_has_its_own_count(make_org: MakeOrg, person: MakePerson) -> None:
    org, other = await make_org(), await make_org("Autre")
    cami = await person(org)
    await add(cami, "ici")
    async with transaction() as session:
        session.add(
            Notification(
                account_id=cami.account.id,
                org_id=other.id,
                type="new_prono",
                dedupe_key="ailleurs",
                payload={"prono_id": "00000000-0000-0000-0000-000000000001", "question": "x"},
            )
        )
    assert (await cami.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1


# The bubbles of the menus


async def bubbles(who: Person, org_id: object) -> dict[str, Any]:
    response = await who.client.get(f"/api/orgs/{org_id}/notifications/unread")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body["total"] == sum(p["unread"] for p in body["pronos"])
    return body


async def on(who: Person, org_id: object) -> dict[str, tuple[str, int]]:
    """Per prono: its state (the list's filter) and its count."""
    return {
        p["prono_id"]: (p["state"], p["unread"]) for p in (await bubbles(who, org_id))["pronos"]
    }


async def open_prono(client: httpx.AsyncClient, org_id: object, prono_id: str) -> None:
    response = await client.post(
        f"/api/orgs/{org_id}/notifications/read", json={"prono_id": prono_id}
    )
    assert response.status_code == 204, response.text


async def test_the_bubbles_lead_to_the_pronos_until_opened(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    first = await publish(hugo.client, str(org.id))
    fake_clock.advance(timedelta(minutes=5))
    second = await publish(hugo.client, str(org.id), question="Le pot aura-t-il lieu ?")

    body = await bubbles(cami, org.id)
    assert body["total"] == 2
    # The most recently notified first, with the state and section that tell under which
    # filters of the list it is.
    section = first["section"]["id"]
    assert [(p["prono_id"], p["state"], p["section_id"], p["unread"]) for p in body["pronos"]] == [
        (second["id"], "open", section, 1),
        (first["id"], "open", section, 1),
    ]
    # Its author is not told of their own prono.
    assert await bubbles(hugo, org.id) == {"total": 0, "pronos": []}

    # Cami opens the first prono: its bubble goes, the other one stays, and so does Léo's.
    await open_prono(cami.client, org.id, first["id"])
    assert await on(cami, org.id) == {second["id"]: ("open", 1)}
    assert (await cami.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 1
    assert (await bubbles(leo, org.id))["total"] == 2
    # Opening it again, or a prono with nothing for her, changes nothing.
    await open_prono(cami.client, org.id, first["id"])
    await open_prono(cami.client, org.id, "00000000-0000-0000-0000-000000000001")
    assert (await bubbles(cami, org.id))["total"] == 1


async def test_a_bubble_lasts_as_long_as_its_news(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    """A new prono and its last two hours while it is open, a reminder while the result waits, a
    result and a tag until read."""
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    closes_at = clock.now() + timedelta(days=1)
    prono = await publish(hugo.client, str(org.id), closes_at=closes_at.isoformat())
    await place(cami.client, str(org.id), prono["id"], option_id=option(prono, "Nice"), stake=10)
    await open_prono(cami.client, org.id, prono["id"])

    # Léo has not played: « nouveau prono », then « plus que 2 h ».
    fake_clock.set(closes_at - timedelta(hours=1))
    assert await closing_soon_alerts() > 0
    assert await on(leo, org.id) == {prono["id"]: ("open", 2)}
    # Closed: there is nothing left for him to play.
    fake_clock.set(closes_at + timedelta(days=1))
    await advance_pronos()
    assert await bubbles(leo, org.id) == {"total": 0, "pronos": []}

    # The result to designate waits for Hugo, under « Clos ».
    assert await designation_reminders() == 1
    assert await on(hugo, org.id) == {prono["id"]: ("closed", 1)}
    # Léo tags Cami in the discussion.
    await write(leo.client, org.id, prono["id"], "Alors @Cami ?", [str(cami.member.id)])
    assert await on(cami, org.id) == {prono["id"]: ("closed", 1)}

    # Designated: Hugo's reminder is over; Cami's result joins her tag, under « Résolus ».
    resolved = await hugo.client.post(
        url(org.id, prono["id"], "resolve"), json={"correct_option_ids": [option(prono, "Nice")]}
    )
    assert resolved.status_code == 200, resolved.text
    assert (await bubbles(hugo, org.id))["total"] == 0
    assert await on(cami, org.id) == {prono["id"]: ("resolved", 2)}
    await open_prono(cami.client, org.id, prono["id"])
    assert (await bubbles(cami, org.id))["total"] == 0


async def test_the_reports_keep_their_own_count(make_org: MakeOrg, person: MakePerson) -> None:
    """The open reports, beside « La rédaction », lead the editor to them: no bubble on the
    prono for the report itself."""
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    reported = await cami.client.post(url(org.id, prono["id"], "reports"), json={"kind": "content"})
    assert reported.status_code == 201, reported.text

    listed = (await ines.client.get(f"/api/orgs/{org.id}/notifications")).json()
    assert sorted(n["type"] for n in listed["items"]) == ["new_prono", "report"]
    assert listed["unread"] == 2
    assert await on(ines, org.id) == {prono["id"]: ("open", 1)}
    # Opening the prono reads both.
    await open_prono(ines.client, org.id, prono["id"])
    assert (await ines.client.get(f"/api/orgs/{org.id}/notifications")).json()["unread"] == 0


async def test_the_app_shows_what_neither_push_nor_e_mail_carried(
    make_org: MakeOrg, person: MakePerson
) -> None:
    """Push and e-mail switched off: the worker skips the notification, the bubble stays until
    the prono is opened."""
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    switched = await cami.client.put(
        "/api/me/notification-prefs",
        json=[
            {"type": "new_prono", "channel": "push", "enabled": False},
            {"type": "new_prono", "channel": "email", "enabled": False},
        ],
    )
    assert switched.status_code == 200, switched.text
    prono = await publish(hugo.client, str(org.id))
    sender = MemorySender()
    await dispatch(sender, Renderer())
    assert sender.sent == []
    assert [n.state for n in await outbox("new_prono")] == ["skipped"]

    assert await on(cami, org.id) == {prono["id"]: ("open", 1)}
    await open_prono(cami.client, org.id, prono["id"])
    assert (await bubbles(cami, org.id))["total"] == 0


async def test_each_newsroom_has_its_own_bubbles(
    make_org: MakeOrg, person: MakePerson, make_member: MakeMember
) -> None:
    org, other = await make_org(), await make_org("Autre")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    await make_member(other, "reader", account=cami.account, pseudo="Cami")
    zoe = await person(other, "journalist", "Zoé")
    here = await publish(hugo.client, str(org.id))
    there = await publish(zoe.client, str(other.id), question="Le pot aura-t-il lieu ?")

    assert await on(cami, org.id) == {here["id"]: ("open", 1)}
    assert await on(cami, other.id) == {there["id"]: ("open", 1)}
    # A prono of the other newsroom is read only there.
    await open_prono(cami.client, org.id, there["id"])
    assert (await bubbles(cami, other.id))["total"] == 1
    await open_prono(cami.client, other.id, there["id"])
    assert (await bubbles(cami, other.id))["total"] == 0
    assert (await bubbles(cami, org.id))["total"] == 1

    # Not a member there: 404, so the newsroom's existence stays private.
    assert (await hugo.client.get(f"/api/orgs/{other.id}/notifications/unread")).status_code == 404
    refused = await hugo.client.post(
        f"/api/orgs/{other.id}/notifications/read", json={"prono_id": there["id"]}
    )
    assert refused.status_code == 404


async def test_the_bubbles_move_on_every_screen_of_the_member(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    """Without a reload: a notification that arrives, and one read on another device, reach the
    member's own topic with the newsroom they are about."""
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    socket = await connect(live_server, cami)

    prono = await publish(hugo.client, str(org.id))
    event = await next_of(socket, "event")
    assert (event["topic"], event["event"], event["data"]) == (
        "me",
        "notification.created",
        {"org_id": str(org.id)},
    )

    async with httpx.AsyncClient(
        base_url=f"http://{live_server}",
        headers={"X-Sibylle": "1", "Origin": ORIGIN},
        cookies={"sibylle_session": cami.client.cookies.get("sibylle_session") or ""},
    ) as phone:
        await open_prono(phone, org.id, prono["id"])
    event = await next_of(socket, "event")
    assert (event["topic"], event["event"], event["data"]) == (
        "me",
        "notification.read",
        {"org_id": str(org.id)},
    )
    await socket.close()


async def test_a_state_change_moves_the_bubbles_of_those_notified(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    """A prono that closes, is cancelled or resolved changes what its unread notifications count
    for: the screens of their members reload the bubbles, the newsroom's own in the lists of
    newsrooms too, which do not follow the newsroom's events. Not the others' screens."""
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    await open_prono(leo.client, org.id, prono["id"])
    cami_screen, hugo_screen, leo_screen = [
        await connect(live_server, who) for who in (cami, hugo, leo)
    ]

    cancelled = await ines.client.post(url(org.id, prono["id"], "cancel"), json={})
    assert cancelled.status_code == 200, cancelled.text
    event = await next_of(cami_screen, "event")
    assert (event["topic"], event["event"], event["data"]) == (
        "me",
        "notification.changed",
        {"org_id": str(org.id)},
    )
    # Its author had nothing about it, Léo had read it: their next event is the next prono.
    await publish(ines.client, str(org.id), question="Le pot aura-t-il lieu ?")
    for screen in (cami_screen, hugo_screen, leo_screen):
        event = await next_of(screen, "event")
        assert (event["topic"], event["event"]) == ("me", "notification.created")
        await screen.close()


async def test_every_editor_follows_the_open_reports(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    """A report filed, then handled by one editor: the others' count beside « La rédaction », and
    the newsroom's bubble, follow on their screens."""
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    lea = await person(org, "editor", "Léa")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    screen = await connect(live_server, lea)

    reported = await cami.client.post(url(org.id, prono["id"], "reports"), json={"kind": "content"})
    assert reported.status_code == 201, reported.text
    report = reported.json()["id"]
    event = await next_event(screen, "report.created")
    assert event["data"] == {
        "report_id": report,
        "prono_id": prono["id"],
        "org_id": str(org.id),
        "kind": "content",
    }
    handled = await ines.client.post(
        f"/api/orgs/{org.id}/reports/{report}/handle", json={"state": "dismissed"}
    )
    assert handled.status_code == 200, handled.text
    event = await next_event(screen, "report.handled")
    assert event["data"] == {
        "report_id": report,
        "prono_id": prono["id"],
        "org_id": str(org.id),
        "state": "dismissed",
    }
    await screen.close()


async def next_event(socket: Any, name: str) -> dict[str, Any]:
    while True:
        event = await next_of(socket, "event")
        if event["event"] == name:
            return event
