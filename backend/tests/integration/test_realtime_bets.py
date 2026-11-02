import asyncio
import json
import time
from datetime import timedelta
from typing import Any

import httpx
import pytest
import websockets
from tests.conftest import ORIGIN, MakeOrg, MakePerson, Person

from sibylle import clock

pytestmark = pytest.mark.integration


async def connect(server: str, who: Person) -> Any:
    token = who.client.cookies.get("sibylle_session")
    return await websockets.connect(
        f"ws://{server}/api/ws",
        origin=ORIGIN,  # type: ignore[arg-type]
        additional_headers={"Cookie": f"sibylle_session={token}"},
    )


async def next_of(socket: Any, kind: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while True:
        message = json.loads(await asyncio.wait_for(socket.recv(), deadline - time.monotonic()))
        if message.get("type") == kind:
            return dict(message)


async def test_a_bet_reaches_the_other_screen_quickly(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader", "Cami")
    sections = (await hugo.client.get(f"/api/orgs/{org.id}/sections")).json()
    prono = (
        await hugo.client.post(
            f"/api/orgs/{org.id}/pronos",
            json={
                "kind": "choice",
                "question": "Nice ou Monaco samedi ?",
                "section_id": sections[0]["id"],
                "options": ["Nice", "Monaco"],
                "base_gain": 20,
                "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
            },
        )
    ).json()

    watcher = await connect(live_server, hugo)
    await watcher.send(json.dumps({"type": "subscribe", "topics": [f"prono:{prono['id']}"]}))
    subscribed = await next_of(watcher, "subscribed")
    assert subscribed["topics"] == [f"prono:{prono['id']}"]

    started = time.monotonic()
    async with httpx.AsyncClient(
        base_url=f"http://{live_server}",
        headers={"X-Sibylle": "1", "Origin": ORIGIN},
        cookies={"sibylle_session": cami.client.cookies.get("sibylle_session") or ""},
    ) as live_cami:
        placed = await live_cami.post(
            f"/api/orgs/{org.id}/pronos/{prono['id']}/bets",
            json={"option_id": prono["options"][0]["id"], "stake": 10},
        )
        assert placed.status_code == 201
    event = await next_of(watcher, "event")
    assert time.monotonic() - started < 2
    assert (event["topic"], event["event"]) == (f"prono:{prono['id']}", "bet.placed")
    assert event["data"]["pot"] == 10 and event["data"]["bet"]["member"]["pseudo"] == "Cami"
    await watcher.close()


async def test_another_newsroom_cannot_follow_the_prono(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    sections = (await hugo.client.get(f"/api/orgs/{org.id}/sections")).json()
    prono = (
        await hugo.client.post(
            f"/api/orgs/{org.id}/pronos",
            json={
                "kind": "yes_no",
                "question": "Neige à Noël ?",
                "section_id": sections[0]["id"],
                "options": [],
                "base_gain": 5,
                "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
            },
        )
    ).json()
    outsider = await person(await make_org(title="Ailleurs"), "editor")
    socket = await connect(live_server, outsider)
    await socket.send(
        json.dumps({"type": "subscribe", "topics": [f"prono:{prono['id']}", f"org:{org.id}"]})
    )
    first = await next_of(socket, "error")
    assert first["code"] == "forbidden_topic"
    subscribed = await next_of(socket, "subscribed")
    assert subscribed["topics"] == []
    await socket.close()
