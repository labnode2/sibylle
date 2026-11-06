import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import ORIGIN, MakeOrg, MakePerson
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url
from tests.integration.test_realtime_bets import connect, next_of

from sibylle import clock

pytestmark = pytest.mark.contract


async def ids(client: Any, org_id: object, state: str) -> list[str]:
    response = await client.get(f"/api/orgs/{org_id}/pronos", params={"state": state})
    assert response.status_code == 200, response.text
    return [p["id"] for p in response.json()["items"]]


async def test_a_reader_proposes_and_a_journalist_validates(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org(max_base_gain=30)
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    proposal = await publish(cami.client, str(org.id), base_gain=10)
    assert proposal["state"] == "proposed"
    assert proposal["created_by"]["pseudo"] == "Cami"
    assert [e["kind"] for e in proposal["events"]] == ["proposed"]

    # Only its author and the journalists see it.
    assert await ids(cami.client, org.id, "proposed") == [proposal["id"]]
    assert await ids(hugo.client, org.id, "proposed") == [proposal["id"]]
    assert await ids(leo.client, org.id, "proposed") == []
    assert (await leo.client.get(url(org.id, proposal["id"]))).status_code == 404
    # Nobody bets on a proposal.
    early = await place(
        cami.client, str(org.id), proposal["id"], option_id=option(proposal, "Nice"), stake=0
    )
    assert early.status_code == 409 and early.json()["error"]["code"] == "invalid_state"

    # Readers cannot validate; the gain stays under the newsroom's ceiling.
    assert (
        await leo.client.post(url(org.id, proposal["id"], "validate"), json={})
    ).status_code == 403
    too_much = await hugo.client.post(
        url(org.id, proposal["id"], "validate"), json={"base_gain": 40}
    )
    assert too_much.status_code == 422 and "base_gain" in too_much.json()["error"]["fields"]

    validated = await hugo.client.post(
        url(org.id, proposal["id"], "validate"), json={"base_gain": 25}
    )
    assert validated.status_code == 200, validated.text
    detail = validated.json()
    assert (detail["state"], detail["base_gain"]) == ("open", 25)
    assert [e["kind"] for e in detail["events"]] == ["proposed", "validated"]
    assert proposal["id"] in await ids(leo.client, org.id, "open")
    again = await hugo.client.post(url(org.id, proposal["id"], "validate"), json={})
    assert again.status_code == 409


async def test_a_proposal_with_a_later_opening_is_scheduled(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    proposal = await publish(
        cami.client, str(org.id), opens_at=(clock.now() + timedelta(hours=2)).isoformat()
    )
    validated = (await hugo.client.post(url(org.id, proposal["id"], "validate"), json={})).json()
    assert (validated["state"], validated["base_gain"]) == ("scheduled", 20)


async def test_a_journalist_rejects_with_a_reason(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    proposal = await publish(cami.client, str(org.id))

    rejected = await ines.client.post(
        url(org.id, proposal["id"], "reject"), json={"reason": "Doublon du prono de lundi"}
    )
    assert rejected.status_code == 200, rejected.text
    # The author is told why.
    mine = (await cami.client.get(url(org.id, proposal["id"]))).json()
    assert (mine["state"], mine["rejected_reason"]) == ("rejected", "Doublon du prono de lundi")
    assert mine["events"][-1]["kind"] == "rejected"
    assert (await leo.client.get(url(org.id, proposal["id"]))).status_code == 404
    assert (
        await ines.client.post(url(org.id, proposal["id"], "reject"), json={})
    ).status_code == 409
    # A journalist's own prono is published, never proposed: nothing to reject.
    published = await publish(ines.client, str(org.id))
    assert (
        await ines.client.post(url(org.id, published["id"], "reject"), json={})
    ).status_code == 409


async def test_a_proposal_reaches_the_journalists_and_its_author_only(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    sockets = {}
    for name, who in (("hugo", hugo), ("cami", cami), ("leo", leo)):
        socket = await connect(live_server, who)
        await socket.send(json.dumps({"type": "subscribe", "topics": [f"org:{org.id}"]}))
        await next_of(socket, "subscribed")
        sockets[name] = socket

    async with httpx.AsyncClient(
        base_url=f"http://{live_server}",
        headers={"X-Sibylle": "1", "Origin": ORIGIN},
        cookies={"sibylle_session": cami.client.cookies.get("sibylle_session") or ""},
    ) as live_cami:
        proposal = await publish(live_cami, str(org.id))

    for name in ("hugo", "cami"):
        event = await next_of(sockets[name], "event")
        assert (event["event"], event["data"]["prono"]["id"]) == ("prono.created", proposal["id"])
    # Léo hears of the next public prono, never of the proposal.
    await publish(hugo.client, str(org.id), question="Le pot aura-t-il lieu ?")
    event = await next_of(sockets["leo"], "event")
    assert event["data"]["prono"]["question"] == "Le pot aura-t-il lieu ?"
    for socket in sockets.values():
        await socket.close()


async def test_reactions(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    react = url(org.id, prono["id"], "reactions")

    assert (await cami.client.put(f"{react}/jackpot")).status_code == 204
    assert (await cami.client.put(f"{react}/jackpot")).status_code == 204  # twice: still one
    assert (await leo.client.put(f"{react}/jackpot")).status_code == 204
    assert (await leo.client.put(f"{react}/enfin")).status_code == 204
    seen_by_cami = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert seen_by_cami["reactions"] == {"jackpot": 2, "enfin": 1}
    assert seen_by_cami["my_reactions"] == ["jackpot"]
    assert sorted((await leo.client.get(url(org.id, prono["id"]))).json()["my_reactions"]) == [
        "enfin",
        "jackpot",
    ]

    # A second press takes it back.
    assert (await cami.client.delete(f"{react}/jackpot")).status_code == 204
    assert (await cami.client.delete(f"{react}/jackpot")).status_code == 204
    seen_by_cami = (await cami.client.get(url(org.id, prono["id"]))).json()
    assert (seen_by_cami["reactions"], seen_by_cami["my_reactions"]) == (
        {"jackpot": 1, "enfin": 1},
        [],
    )

    assert (await cami.client.put(f"{react}/colere")).status_code == 422
    proposal = await publish(cami.client, str(org.id))
    on_proposal = await cami.client.put(f"{url(org.id, proposal['id'], 'reactions')}/yes")
    assert on_proposal.status_code == 409
    outsider = await person(await make_org("Autre rédaction"))
    assert (await outsider.client.put(f"{react}/yes")).status_code == 404
