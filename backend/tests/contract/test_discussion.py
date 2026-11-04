"""US14: the discussion under a prono, its likes, and who may delete what (spec FR-140 to
FR-143, research.md J9)."""

import json
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import assert_no_private_data
from tests.contract.test_data_rights import delete_me
from tests.contract.test_pronos import publish
from tests.contract.test_results import url
from tests.integration.test_realtime_bets import connect, next_of

from sibylle.db.models import MessageLike
from sibylle.db.session import transaction
from sibylle.services.accounts import ANONYMOUS_PSEUDO

pytestmark = pytest.mark.contract

HINT = "Monaco n'a pas gagné à Nice depuis 2019."


def messages_url(org_id: object, prono_id: str, *rest: str) -> str:
    return "/".join([url(org_id, prono_id, "messages"), *rest])


async def write(
    client: httpx.AsyncClient, org_id: object, prono_id: str, body: str
) -> dict[str, Any]:
    response = await client.post(messages_url(org_id, prono_id), json={"body": body})
    assert response.status_code == 201, response.text
    message: dict[str, Any] = response.json()
    return message


async def read(
    client: httpx.AsyncClient, org_id: object, prono_id: str, **params: Any
) -> dict[str, Any]:
    response = await client.get(messages_url(org_id, prono_id), params=params)
    assert response.status_code == 200, response.text
    page: dict[str, Any] = response.json()
    assert_no_private_data(page)
    return page


async def count_of(client: httpx.AsyncClient, org_id: object, prono_id: str) -> int:
    """The number of messages, as the prono, the list and la une give it."""
    detail = (await client.get(url(org_id, prono_id))).json()
    listed = (await client.get(f"/api/orgs/{org_id}/pronos", params={"state": "open"})).json()
    [summary] = [p for p in listed["items"] if p["id"] == prono_id]
    front = (await client.get(f"/api/orgs/{org_id}/front-page")).json()
    [headline] = [p for p in [front["headline"], *front["open"]] if p and p["id"] == prono_id]
    assert detail["message_count"] == summary["message_count"] == headline["message_count"]
    value: int = detail["message_count"]
    return value


async def test_members_write_under_a_prono(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    assert await count_of(cami.client, org.id, prono["id"]) == 0

    mine = await write(cami.client, org.id, prono["id"], f"  {HINT}\n")
    assert (mine["body"], mine["author"]["pseudo"], mine["likes"], mine["liked"]) == (
        HINT,
        "Cami",
        0,
        False,
    )
    assert (mine["likers"], mine["can_delete"]) == ([], True)
    await write(leo.client, org.id, prono["id"], "Allez Nice !\nOn y croit.")

    page = await read(leo.client, org.id, prono["id"])
    assert [(m["author"]["pseudo"], m["body"]) for m in page["items"]] == [
        ("Cami", HINT),
        ("Léo", "Allez Nice !\nOn y croit."),
    ]
    assert [m["can_delete"] for m in page["items"]] == [False, True]
    assert page["has_more"] is False
    assert await count_of(hugo.client, org.id, prono["id"]) == 2

    # Nothing but spaces, or more than 500 characters, is refused; 500 is fine.
    for body, problem in (("   \n ", "empty"), ("x" * 501, "too_long")):
        refused = await cami.client.post(messages_url(org.id, prono["id"]), json={"body": body})
        assert refused.status_code == 422, refused.text
        assert refused.json()["error"]["fields"] == {"body": problem}
    await write(cami.client, org.id, prono["id"], "x" * 500)

    # Another newsroom sees nothing.
    outsider = await person(await make_org("Autre rédaction"))
    assert (await outsider.client.get(messages_url(org.id, prono["id"]))).status_code == 404
    posted = await outsider.client.post(messages_url(org.id, prono["id"]), json={"body": "Coucou"})
    assert posted.status_code == 404


async def test_a_long_discussion_comes_twenty_at_a_time(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    prono = await publish(hugo.client, str(org.id))
    for n in range(1, 26):
        await write(hugo.client, org.id, prono["id"], f"Message {n}")

    latest = await read(hugo.client, org.id, prono["id"])
    assert [m["body"] for m in latest["items"]] == [f"Message {n}" for n in range(6, 26)]
    assert latest["has_more"] is True
    older = await read(hugo.client, org.id, prono["id"], before=latest["items"][0]["id"])
    assert [m["body"] for m in older["items"]] == [f"Message {n}" for n in range(1, 6)]
    assert older["has_more"] is False
    few = await read(hugo.client, org.id, prono["id"], limit=3)
    assert ([m["body"] for m in few["items"]], few["has_more"]) == (
        ["Message 23", "Message 24", "Message 25"],
        True,
    )
    too_many = await hugo.client.get(messages_url(org.id, prono["id"]), params={"limit": 51})
    assert too_many.status_code == 422


async def test_liking_a_message(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    message = await write(cami.client, org.id, prono["id"], HINT)
    like = messages_url(org.id, prono["id"], message["id"], "like")

    assert (await leo.client.put(like)).status_code == 204
    assert (await leo.client.put(like)).status_code == 204  # twice: still one
    assert (await hugo.client.put(like)).status_code == 204
    [seen_by_cami] = (await read(cami.client, org.id, prono["id"]))["items"]
    assert (seen_by_cami["likes"], seen_by_cami["liked"], seen_by_cami["likers"]) == (
        2,
        False,
        ["Léo", "Hugo"],
    )
    [seen_by_leo] = (await read(leo.client, org.id, prono["id"]))["items"]
    assert seen_by_leo["liked"] is True

    # A second press takes it back; one's own message may be liked too.
    assert (await leo.client.delete(like)).status_code == 204
    assert (await leo.client.delete(like)).status_code == 204
    assert (await cami.client.put(like)).status_code == 204
    [seen] = (await read(leo.client, org.id, prono["id"]))["items"]
    assert (seen["likes"], seen["liked"], seen["likers"]) == (2, False, ["Hugo", "Cami"])

    unknown = messages_url(org.id, prono["id"], prono["id"], "like")
    assert (await leo.client.put(unknown)).status_code == 404


async def test_authors_delete_their_messages_and_the_editor_moderates(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    prono = await publish(hugo.client, str(org.id))
    first = await write(cami.client, org.id, prono["id"], HINT)
    second = await write(hugo.client, org.id, prono["id"], "Hors charte !")
    assert (
        await leo.client.put(messages_url(org.id, prono["id"], first["id"], "like"))
    ).status_code == 204
    [_, seen_by_ines] = (await read(ines.client, org.id, prono["id"]))["items"]
    assert seen_by_ines["can_delete"] is True

    # Only its author, or the editor: neither a reader nor a journalist for someone else's.
    for other in (leo, hugo):
        refused = await other.client.delete(messages_url(org.id, prono["id"], first["id"]))
        assert refused.status_code == 403
    assert (
        await cami.client.delete(messages_url(org.id, prono["id"], first["id"]))
    ).status_code == 204
    async with transaction() as session:
        assert await session.scalar(select(func.count()).select_from(MessageLike)) == 0
    assert (
        await ines.client.delete(messages_url(org.id, prono["id"], second["id"]))
    ).status_code == 204
    again = await ines.client.delete(messages_url(org.id, prono["id"], second["id"]))
    assert again.status_code == 404
    assert (await read(leo.client, org.id, prono["id"]))["items"] == []
    assert await count_of(leo.client, org.id, prono["id"]) == 0
    # A deleted message cannot be liked any more.
    gone = await leo.client.put(messages_url(org.id, prono["id"], second["id"], "like"))
    assert gone.status_code == 404


async def test_the_discussion_opens_with_the_publication(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    proposal = await publish(cami.client, str(org.id))
    assert proposal["state"] == "proposed"

    refused = await cami.client.post(messages_url(org.id, proposal["id"]), json={"body": HINT})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "invalid_state")
    read_by_journalist = await hugo.client.get(messages_url(org.id, proposal["id"]))
    assert (read_by_journalist.status_code, read_by_journalist.json()["error"]["code"]) == (
        409,
        "invalid_state",
    )
    assert (await leo.client.get(messages_url(org.id, proposal["id"]))).status_code == 404


async def test_messages_and_likes_reach_the_screens_live(
    make_org: MakeOrg, person: MakePerson, live_server: str
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    socket = await connect(live_server, hugo)
    await socket.send(json.dumps({"type": "subscribe", "topics": [f"prono:{prono['id']}"]}))
    await next_of(socket, "subscribed")

    message = await write(cami.client, org.id, prono["id"], HINT)
    posted = await next_of(socket, "event")
    assert (posted["event"], posted["data"]) == (
        "message.posted",
        {"prono_id": prono["id"], "message_id": message["id"], "message_count": 1},
    )
    await hugo.client.put(messages_url(org.id, prono["id"], message["id"], "like"))
    liked = await next_of(socket, "event")
    assert (liked["event"], liked["data"]) == (
        "message.liked",
        {"prono_id": prono["id"], "message_id": message["id"], "likes": 1},
    )
    await cami.client.delete(messages_url(org.id, prono["id"], message["id"]))
    deleted = await next_of(socket, "event")
    assert (deleted["event"], deleted["data"]["message_count"]) == ("message.deleted", 0)
    await socket.close()


async def test_my_messages_are_exported_and_go_with_my_account(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    mine = await write(cami.client, org.id, prono["id"], HINT)
    theirs = await write(hugo.client, org.id, prono["id"], "Pas si sûr.")
    await hugo.client.put(messages_url(org.id, prono["id"], mine["id"], "like"))
    await cami.client.put(messages_url(org.id, prono["id"], theirs["id"], "like"))

    export = (await cami.client.get("/api/me/export")).json()
    [newsroom] = export["newsrooms"]
    assert [(m["prono_id"], m["body"], m["likes"]) for m in newsroom["messages"]] == [
        (prono["id"], HINT, 1)
    ]

    # Her messages go; her like stays, under « Ancien membre ».
    assert (await delete_me(cami.client)).status_code == 204
    [left] = (await read(hugo.client, org.id, prono["id"]))["items"]
    assert (left["body"], left["likes"], left["likers"]) == ("Pas si sûr.", 1, [ANONYMOUS_PSEUDO])
