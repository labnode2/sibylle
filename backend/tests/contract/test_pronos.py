import asyncio
import io
from datetime import timedelta
from typing import Any

import httpx
import pytest
from PIL import Image
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import assert_no_private_data

from sibylle import clock
from sibylle.worker.jobs import advance_pronos

pytestmark = pytest.mark.contract


async def section_id(client: httpx.AsyncClient, org_id: str) -> str:
    sections = (await client.get(f"/api/orgs/{org_id}/sections")).json()
    assert [s["name"] for s in sections] == ["Général"]
    return str(sections[0]["id"])


async def publish(client: httpx.AsyncClient, org_id: str, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "choice",
        "question": "Nice ou Monaco samedi ?",
        "section_id": await section_id(client, org_id),
        "options": ["Nice", "Nul", "Monaco"],
        "base_gain": 20,
        "closes_at": (clock.now() + timedelta(days=3)).isoformat(),
    }
    body.update(changes)
    response = await client.post(f"/api/orgs/{org_id}/pronos", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def place(
    client: httpx.AsyncClient, org_id: str, prono_id: str, **body: Any
) -> httpx.Response:
    return await client.post(f"/api/orgs/{org_id}/pronos/{prono_id}/bets", json=body)


async def balance(client: httpx.AsyncClient, org_id: str) -> int:
    value: int = (await client.get(f"/api/orgs/{org_id}")).json()["my_membership"]["balance"]
    return value


async def test_a_journalist_publishes_a_prono(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    prono = await publish(hugo.client, str(org.id))
    assert (prono["state"], prono["base_gain"], prono["bet_count"], prono["pot"]) == (
        "open",
        20,
        0,
        0,
    )
    assert [o["label"] for o in prono["options"]] == ["Nice", "Nul", "Monaco"]
    assert prono["created_by"]["pseudo"] == "Hugo"
    assert prono["section"]["name"] == "Général"

    later = await publish(
        hugo.client, str(org.id), opens_at=(clock.now() + timedelta(hours=2)).isoformat()
    )
    assert later["state"] == "scheduled"

    yes_no = await publish(hugo.client, str(org.id), kind="yes_no", options=[])
    assert [o["label"] for o in yes_no["options"]] == ["Oui", "Non"]


async def test_each_newsroom_numbers_its_pronos(make_org: MakeOrg, person: MakePerson) -> None:
    """« PRONO N° 128 »: one count per newsroom, proposals included, never twice the same."""
    org = await make_org()
    other = await make_org("Autre rédaction")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    stranger = await person(other, "journalist", "Inconnu")
    first = await publish(hugo.client, str(org.id))
    proposal = await publish(cami.client, str(org.id), question="Une idée de Cami ?")
    elsewhere = await publish(stranger.client, str(other.id))
    concurrent = await asyncio.gather(*(publish(hugo.client, str(org.id)) for _ in range(4)))
    assert (first["number"], proposal["number"], elsewhere["number"]) == (1, 2, 1)
    assert sorted(p["number"] for p in concurrent) == [3, 4, 5, 6]
    listed = (await hugo.client.get(f"/api/orgs/{org.id}/pronos", params={"state": "open"})).json()
    assert sorted(p["number"] for p in listed["items"]) == [1, 3, 4, 5, 6]


async def test_publishing_is_checked(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org(max_base_gain=30)
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    sid = await section_id(hugo.client, str(org.id))
    body = {
        "kind": "choice",
        "question": "Qui gagne ?",
        "section_id": sid,
        "options": ["A", "B"],
        "base_gain": 40,
        "closes_at": (clock.now() + timedelta(days=1)).isoformat(),
    }
    too_much = await hugo.client.post(f"/api/orgs/{org.id}/pronos", json=body)
    assert too_much.status_code == 422 and "base_gain" in too_much.json()["error"]["fields"]
    # A reader's prono waits for a journalist (US5), under the same checks.
    reader = await cami.client.post(f"/api/orgs/{org.id}/pronos", json={**body, "base_gain": 10})
    assert reader.status_code == 201 and reader.json()["state"] == "proposed"
    over = await cami.client.post(f"/api/orgs/{org.id}/pronos", json=body)
    assert over.status_code == 422 and "base_gain" in over.json()["error"]["fields"]


async def test_betting_with_a_stake(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    prono = await publish(hugo.client, str(org.id))
    nice, monaco = prono["options"][0]["id"], prono["options"][2]["id"]

    placed = await place(cami.client, str(org.id), prono["id"], option_id=nice, stake=20)
    assert placed.status_code == 201
    assert (placed.json()["stake"], placed.json()["rank"], placed.json()["answer"]) == (
        20,
        1,
        "Nice",
    )
    assert await balance(cami.client, str(org.id)) == 80

    await place(hugo.client, str(org.id), prono["id"], option_id=monaco, stake=0)
    detail = (await cami.client.get(f"/api/orgs/{org.id}/pronos/{prono['id']}")).json()
    assert (detail["pot"], detail["bet_count"]) == (20, 2)
    by_label = {o["label"]: o for o in detail["options"]}
    assert (by_label["Nice"]["count"], by_label["Nice"]["stake_total"]) == (1, 20)
    assert by_label["Nice"]["share_pct"] == 50 and by_label["Nul"]["share_pct"] == 0
    assert [(b["member"]["pseudo"], b["answer"], b["stake"]) for b in detail["bets"]] == [
        ("Cami", "Nice", 20),
        ("Hugo", "Monaco", 0),
    ]
    assert detail["my_bet"]["answer"] == "Nice"
    assert detail["can_edit"] is False
    assert_no_private_data(detail)

    again = await place(cami.client, str(org.id), prono["id"], option_id=monaco, stake=0)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_bet"

    leo = await person(org, "reader")
    broke = await place(leo.client, str(org.id), prono["id"], option_id=nice, stake=101)
    assert broke.json()["error"]["code"] == "insufficient_balance"
    unknown = await place(leo.client, str(org.id), prono["id"], option_id=prono["id"], stake=0)
    assert unknown.status_code == 422


async def test_editing_stops_at_the_first_bet(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await publish(hugo.client, str(org.id))
    url = f"/api/orgs/{org.id}/pronos/{prono['id']}"
    edited = await hugo.client.patch(url, json={"question": "Nice ou Monaco dimanche ?"})
    assert edited.status_code == 200 and edited.json()["question"] == "Nice ou Monaco dimanche ?"
    assert (await cami.client.patch(url, json={"question": "Pas moi ?"})).status_code == 403

    await place(
        cami.client, str(org.id), prono["id"], option_id=edited.json()["options"][0]["id"], stake=0
    )
    refused = await hugo.client.patch(url, json={"question": "Trop tard ?"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "invalid_state"


async def test_closing_stops_the_bets(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await publish(
        hugo.client, str(org.id), closes_at=(clock.now() + timedelta(hours=1)).isoformat()
    )
    fake_clock.advance(timedelta(hours=1))
    late = await place(
        cami.client, str(org.id), prono["id"], option_id=prono["options"][0]["id"], stake=0
    )
    assert late.json()["error"]["code"] == "invalid_state"
    assert await advance_pronos() == 1
    detail = (await cami.client.get(f"/api/orgs/{org.id}/pronos/{prono['id']}")).json()
    assert detail["state"] == "closed"


async def test_scheduled_pronos_open_on_time(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    prono = await publish(
        hugo.client, str(org.id), opens_at=(clock.now() + timedelta(hours=1)).isoformat()
    )
    assert await advance_pronos() == 0
    fake_clock.advance(timedelta(hours=1))
    assert await advance_pronos() == 1
    detail = (await hugo.client.get(f"/api/orgs/{org.id}/pronos/{prono['id']}")).json()
    assert detail["state"] == "open"


async def test_number_and_date_bets(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    goals = await publish(hugo.client, str(org.id), kind="number", options=[], number_unit="buts")
    ok = await place(cami.client, str(org.id), goals["id"], number_value="3", stake=5)
    assert ok.status_code == 201 and ok.json()["answer"] == "3 buts"
    wrong = await place(hugo.client, str(org.id), goals["id"], option_id=goals["id"], stake=0)
    assert wrong.status_code == 422

    day = await publish(hugo.client, str(org.id), kind="date", options=[])
    target = (clock.now() + timedelta(days=10)).date().isoformat()
    assert (
        await place(cami.client, str(org.id), day["id"], date_value=target, stake=0)
    ).status_code == 201
    detail = (await cami.client.get(f"/api/orgs/{org.id}/pronos/{day['id']}")).json()
    assert detail["distribution"][0]["count"] == 1


async def test_an_open_ended_date_can_be_bet_again(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    cami = await person(org, "reader")
    prono = await publish(
        hugo.client, str(org.id), kind="date", options=[], open_ended=True, closes_at=None
    )
    assert prono["closes_at"] is None and prono["open_ended"] is True
    tomorrow = (clock.now() + timedelta(days=1)).date().isoformat()
    await place(cami.client, str(org.id), prono["id"], date_value=tomorrow, stake=10)
    early = await place(cami.client, str(org.id), prono["id"], date_value=tomorrow, stake=0)
    assert early.json()["error"]["code"] == "already_bet"

    fake_clock.advance(timedelta(days=2))
    url = f"/api/orgs/{org.id}/pronos/{prono['id']}"
    assert (await cami.client.get(url)).json()["can_rebet"] is True
    later = (clock.now() + timedelta(days=3)).date().isoformat()
    again = await place(cami.client, str(org.id), prono["id"], date_value=later, stake=15)
    assert again.status_code == 201 and again.json()["rank"] == 2
    detail = (await cami.client.get(url)).json()
    assert detail["pot"] == 25  # the first stake stays in the pot
    assert detail["my_bet"]["date_value"] == later
    assert [b["superseded"] for b in detail["bets"]] == [True, False]  # by rank
    assert await balance(cami.client, str(org.id)) == 75


async def test_lists_filter_and_page(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    first = await publish(hugo.client, str(org.id), question="Premier prono ?")
    await publish(hugo.client, str(org.id), question="Deuxième prono ?")
    await publish(
        hugo.client,
        str(org.id),
        question="Plus tard ?",
        opens_at=(clock.now() + timedelta(hours=5)).isoformat(),
    )
    url = f"/api/orgs/{org.id}/pronos"
    opened = (await hugo.client.get(url, params={"state": "open"})).json()
    assert len(opened["items"]) == 2
    page = (await hugo.client.get(url, params={"limit": 2})).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = (await hugo.client.get(url, params={"limit": 2, "cursor": page["next_cursor"]})).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    ids = [p["id"] for p in page["items"] + rest["items"]]
    assert sorted(ids) == sorted(set(ids)) and first["id"] in ids
    by_section = (await hugo.client.get(url, params={"section": first["section"]["id"]})).json()
    assert len(by_section["items"]) == 3


def png(size: tuple[int, int] = (2400, 1200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (74, 80, 208)).save(buffer, "PNG")
    return buffer.getvalue()


async def test_uploads(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    uploaded = await hugo.client.post(
        f"/api/orgs/{org.id}/uploads", files={"file": ("affiche.png", png(), "image/png")}
    )
    assert uploaded.status_code == 201
    image = uploaded.json()
    assert (image["width"], image["height"]) == (1200, 600)
    served = await hugo.client.get(f"/api/orgs/{org.id}/uploads/{image['id']}")
    assert served.status_code == 200 and served.headers["content-type"] == "image/webp"
    assert "private" in served.headers["cache-control"]

    prono = await publish(hugo.client, str(org.id), image_id=image["id"])
    assert prono["image_url"].endswith(f"/uploads/{image['id']}")

    huge = await hugo.client.post(
        f"/api/orgs/{org.id}/uploads",
        files={"file": ("gros.png", b"\0" * (5 * 1024 * 1024 + 1), "image/png")},
    )
    assert huge.status_code == 413 and huge.json()["error"]["code"] == "too_large"
    not_image = await hugo.client.post(
        f"/api/orgs/{org.id}/uploads", files={"file": ("x.png", b"pas une image", "image/png")}
    )
    assert not_image.status_code == 422


async def test_outsiders_get_404(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    hugo = await person(org, "journalist")
    prono = await publish(hugo.client, str(org.id))
    other = await make_org(title="Ailleurs")
    outsider = await person(other, "editor")
    base = f"/api/orgs/{org.id}"
    responses = [
        await outsider.client.get(f"{base}/pronos"),
        await outsider.client.get(f"{base}/pronos/{prono['id']}"),
        await outsider.client.get(f"{base}/sections"),
        await outsider.client.post(f"{base}/pronos", json={}),
        await place(
            outsider.client, str(org.id), prono["id"], option_id=prono["options"][0]["id"], stake=0
        ),
        await outsider.client.post(
            f"{base}/uploads", files={"file": ("a.png", png((4, 4)), "image/png")}
        ),
    ]
    assert [r.status_code for r in responses] == [404] * 6
    # A prono of another newsroom does not exist under this one either.
    wrong_org = await outsider.client.get(f"/api/orgs/{other.id}/pronos/{prono['id']}")
    assert wrong_org.status_code == 404
