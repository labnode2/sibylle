from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select, update
from tests.conftest import MakeOrg, MakePerson
from tests.contract.helpers import AVATAR, assert_no_private_data
from tests.contract.test_pronos import place, publish
from tests.contract.test_results import option, url

from sibylle import clock
from sibylle.db.models import Membership, SecretCode
from sibylle.db.session import transaction
from sibylle.domain.pixels import decode, encode
from sibylle.services.collection import add_secret_code
from sibylle.worker.jobs import advance_pronos, close_finished_seasons

pytestmark = pytest.mark.contract

PARIS = ZoneInfo("Europe/Paris")


def org_url(org_id: object, path: str = "") -> str:
    return f"/api/orgs/{org_id}{path}"


def painted(color: int, size: int = 16) -> dict[str, Any]:
    """The template avatar with one pixel in another colour."""
    pixels = bytearray(decode(AVATAR))
    pixels[0] = color
    assert len(pixels) == size * size
    return encode(size, bytes(pixels))


async def catalog(client: httpx.AsyncClient, org_id: object) -> dict[str, dict[str, Any]]:
    response = await client.get(org_url(org_id, "/catalog"))
    assert response.status_code == 200, response.text
    return {entry["item"]["key"]: entry for entry in response.json()}


async def buy(client: httpx.AsyncClient, org_id: object, key: str) -> httpx.Response:
    items = await catalog(client, org_id)
    return await client.post(org_url(org_id, f"/catalog/{items[key]['item']['id']}/purchase"))


async def me(client: httpx.AsyncClient, org_id: object) -> dict[str, Any]:
    body: dict[str, Any] = (await client.get(org_url(org_id))).json()["my_membership"]
    return body


async def test_the_press_card(
    make_org: MakeOrg, person: MakePerson, fake_clock: clock.FakeClock
) -> None:
    org = await make_org(early_bird_pct=0)
    org_id = str(org.id)
    ines = await person(org, "editor", "Inès")
    hugo = await person(org, "journalist", "Hugo")
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")

    won = await publish(hugo.client, org_id, question="Nice ou Monaco ?")
    lost = await publish(hugo.client, org_id, question="Le pot aura-t-il lieu ?")
    pending = await publish(
        hugo.client,
        org_id,
        question="Qui gagne le baby-foot ?",
        closes_at=(clock.now() + timedelta(days=10)).isoformat(),
    )
    await place(cami.client, org_id, won["id"], option_id=option(won, "Nice"), stake=10)
    await place(leo.client, org_id, won["id"], option_id=option(won, "Monaco"), stake=10)
    await place(cami.client, org_id, lost["id"], option_id=option(lost, "Nul"), stake=0)
    await place(cami.client, org_id, pending["id"], option_id=option(pending, "Nice"), stake=0)
    fake_clock.advance(timedelta(days=4))
    await advance_pronos()
    for prono, answer in ((won, "Nice"), (lost, "Monaco")):
        resolved = await hugo.client.post(
            url(org.id, prono["id"], "resolve"),
            json={"correct_option_ids": [option(prono, answer)]},
        )
        assert resolved.status_code == 200, resolved.text
    assert (await buy(cami.client, org.id, "color-33")).status_code == 201

    fake_clock.set(datetime(2026, 12, 21, 0, 0, 30, tzinfo=PARIS))
    assert await close_finished_seasons() == 1

    # Léo looks at Cami's card: everything public, nothing private.
    response = await leo.client.get(org_url(org.id, f"/members/{cami.member.id}"))
    assert response.status_code == 200, response.text
    card = response.json()
    assert_no_private_data(card)
    assert "balance" not in card
    assert (card["pseudo"], card["role"], card["card_number"]) == ("Cami", "reader", "0003")
    assert card["stats"] == {
        "laurels": 30,  # 20 base + 10 of profit, engraved on the autumn trophy
        "pronos_played": 3,
        "settled": 2,
        "wins": 1,
        "success_rate": 50,
    }
    assert [(t["season"], t["score"], t["rank"], t["podium"]) for t in card["trophies"]] == [
        ({"year": 2026, "name": "autumn"}, 30, 1, True)
    ]
    assert [(c["item"]["key"], c["source"]) for c in card["collection"]] == [
        ("color-33", "purchase")
    ]
    hugos = (await leo.client.get(org_url(org.id, f"/members/{hugo.member.id}"))).json()
    assert (hugos["card_number"], hugos["stats"]["success_rate"]) == ("0002", None)

    # Members who left and other newsrooms' members have no card here. (Inès asks: the others'
    # sessions, last used in November, ran out during the jump to December.)
    async with transaction() as session:
        await session.execute(
            update(Membership).where(Membership.id == leo.member.id).values(status="left")
        )
    assert (await ines.client.get(org_url(org.id, f"/members/{leo.member.id}"))).status_code == 404
    outsider = await person(await make_org("Autre rédaction"))
    assert (
        await outsider.client.get(org_url(org.id, f"/members/{cami.member.id}"))
    ).status_code == 404


async def test_the_catalog_and_purchases(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    items = await catalog(cami.client, org.id)
    assert (items["color-33"]["price"], items["color-33"]["owned"]) == (40, False)
    assert (items["frame-ink"]["price"], items["ball-winter"]["price"]) == (60, 80)
    assert {k for k in items if k.startswith("ball-")} == {
        "ball-spring",
        "ball-summer",
        "ball-autumn",
        "ball-winter",
    }
    # Surprises of the secret codes are not on sale.
    assert "color-49" not in items and "ball-halloween" not in items

    bought = await buy(cami.client, org.id, "color-33")
    assert bought.status_code == 201, bought.text
    assert (bought.json()["owned_item"]["item"]["key"], bought.json()["balance"]) == (
        "color-33",
        60,
    )
    mine = await me(cami.client, org.id)
    assert (mine["balance"], mine["season_score"], mine["unlocked_colors"]) == (60, 0, [33])
    assert (await catalog(cami.client, org.id))["color-33"]["owned"] is True
    statement = (await cami.client.get(org_url(org.id, "/members/me/ledger"))).json()["items"]
    assert (statement[0]["kind"], statement[0]["amount"], statement[0]["reason"]) == (
        "purchase",
        -40,
        "color-33",
    )

    again = await buy(cami.client, org.id, "color-33")
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_state"
    too_dear = await buy(cami.client, org.id, "ball-winter")
    assert too_dear.status_code == 409
    assert too_dear.json()["error"]["code"] == "insufficient_balance"
    assert (await me(cami.client, org.id))["balance"] == 60


async def test_avatars_use_unlocked_colours_and_owned_frames(
    make_org: MakeOrg, person: MakePerson
) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    profile = org_url(org.id, "/members/me")

    locked = await cami.client.patch(profile, json={"avatar": painted(33)})
    assert locked.status_code == 422 and "avatar" in locked.json()["error"]["fields"]
    assert (await buy(cami.client, org.id, "color-33")).status_code == 201
    drawn = await cami.client.patch(profile, json={"avatar": painted(33)})
    assert drawn.status_code == 200, drawn.text
    big = await cami.client.patch(profile, json={"avatar": encode(32, bytes([33] * 1024))})
    assert big.status_code == 200 and big.json()["avatar"]["size"] == 32
    assert (await cami.client.patch(profile, json={"avatar": painted(49)})).status_code == 422

    frame_id = (await catalog(cami.client, org.id))["frame-ink"]["item"]["id"]
    unowned = await cami.client.patch(profile, json={"avatar_frame_item_id": frame_id})
    assert unowned.status_code == 422
    leos_frame = await buy(leo.client, org.id, "frame-ink")
    assert leos_frame.status_code == 201
    framed = await leo.client.patch(profile, json={"avatar_frame_item_id": frame_id})
    assert framed.status_code == 200 and framed.json()["frame"] == "frame-ink"
    # Everyone sees the new avatar and frame.
    members = {m["pseudo"]: m for m in (await cami.client.get(org_url(org.id, "/members"))).json()}
    assert members["Léo"]["frame"] == "frame-ink"
    assert members["Cami"]["avatar"]["size"] == 32
    unframed = await leo.client.patch(profile, json={"avatar_frame_item_id": None})
    assert unframed.json()["frame"] is None


async def test_secret_codes(make_org: MakeOrg, person: MakePerson) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    leo = await person(org, "reader", "Léo")
    manon = await person(org, "reader", "Manon")
    async with transaction() as session:
        await add_secret_code(session, "BOUH-2026", "ball-halloween")
        stored = (await session.scalars(select(SecretCode.code_hash))).all()
    assert "BOUH-2026" not in stored  # only a fingerprint is kept
    redeem = org_url(org.id, "/secret-codes/redeem")

    unlocked = await cami.client.post(redeem, json={"code": "  bouh-2026 "})
    assert unlocked.status_code == 201, unlocked.text
    assert unlocked.json()["item"]["key"] == "ball-halloween"
    twice = await cami.client.post(redeem, json={"code": "BOUH-2026"})
    assert twice.status_code == 409 and twice.json()["error"]["code"] == "invalid_state"
    assert (await leo.client.post(redeem, json={"code": "BOUH-2026"})).status_code == 201
    collection = (await cami.client.get(org_url(org.id, f"/members/{cami.member.id}"))).json()[
        "collection"
    ]
    assert [(c["item"]["key"], c["source"]) for c in collection] == [
        ("ball-halloween", "secret_code")
    ]

    for attempt in range(5):
        wrong = await manon.client.post(redeem, json={"code": f"FAUX-{attempt}"})
        assert wrong.status_code == 422, wrong.text
    blocked = await manon.client.post(redeem, json={"code": "BOUH-2026"})
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"
