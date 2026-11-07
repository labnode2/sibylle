"""US15: a press card its member makes public, seen by anyone with its link, without an account,
also from another site's iframe (spec FR-144 to FR-146, research.md J11)."""

from typing import Any

import httpx
import pytest
from tests.conftest import ClientFor, MakeAccount, MakeOrg, MakePerson
from tests.contract.helpers import AVATAR, assert_no_private_data, create_org
from tests.contract.test_data_rights import delete_me, leave
from tests.contract.test_profile_collection import me, org_url

from sibylle.api.deps import RateLimiter
from sibylle.domain.content import DEFAULT_LOGO

pytestmark = pytest.mark.contract

# What the public card holds: the card itself and its figures, nothing more.
CARD_KEYS = {
    "newsroom",
    "pseudo",
    "avatar",
    "frame",
    "animation",
    "role",
    "joined_at",
    "card_number",
    "stats",
    "showcase",
}


async def make_public(client: httpx.AsyncClient, org_id: object, public: bool) -> dict[str, Any]:
    response = await client.patch(org_url(org_id, "/members/me"), json={"card_public": public})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def public_url(token: str) -> str:
    return f"/api/public/cards/{token}"


async def test_a_card_goes_public_then_private_and_keeps_its_address(
    make_org: MakeOrg, person: MakePerson, client: httpx.AsyncClient
) -> None:
    org = await make_org()
    ines = await person(org, "editor", "Inès")
    cami = await person(org, "journalist", "Cami")

    # Private at first, without an address.
    mine = await me(cami.client, org.id)
    assert (mine["card_public"], mine["card_token"]) == (False, None)

    # Public: an address, and the card for anyone, without an account.
    mine = await make_public(cami.client, org.id, True)
    token = mine["card_token"]
    assert mine["card_public"] is True and token
    assert mine["pseudo"] == "Cami"
    response = await client.get(public_url(token))
    assert response.status_code == 200, response.text
    card = response.json()
    assert set(card) == CARD_KEYS
    assert_no_private_data(card)
    assert card["newsroom"] == {"title": "Sophia Office", "logo": DEFAULT_LOGO}
    assert (card["pseudo"], card["role"], card["card_number"]) == ("Cami", "journalist", "0002")
    assert card["stats"] == {
        "laurels": 0,
        "pronos_played": 0,
        "settled": 0,
        "wins": 0,
        "success_rate": None,
        "streak": 0,
        "best_streak": 0,
    }
    assert card["showcase"] == []

    # Inès's card stays private; once public, it has an address of its own.
    assert (await me(ines.client, org.id))["card_public"] is False
    assert (await make_public(ines.client, org.id, True))["card_token"] != token

    # Private again: the link shows nothing, as one that never existed.
    mine = await make_public(cami.client, org.id, False)
    assert (mine["card_public"], mine["card_token"]) == (False, token)
    for address in (token, "jamais-vu"):
        hidden = await client.get(public_url(address))
        assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "not_found"

    # Public once more: the same address, so that a link or an iframe shows the card again.
    assert (await make_public(cami.client, org.id, True))["card_token"] == token
    assert (await client.get(public_url(token))).status_code == 200


async def test_the_other_settings_stay_as_they_are(
    make_org: MakeOrg, person: MakePerson, client: httpx.AsyncClient
) -> None:
    org = await make_org()
    cami = await person(org, "reader", "Cami")
    token = (await make_public(cami.client, org.id, True))["card_token"]
    renamed = await cami.client.patch(org_url(org.id, "/members/me"), json={"pseudo": "Camille"})
    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["card_public"], renamed.json()["card_token"]) == (True, token)
    assert (await client.get(public_url(token))).json()["pseudo"] == "Camille"


async def test_leaving_the_newsroom_makes_the_card_private(
    make_account: MakeAccount, client_for: ClientFor, client: httpx.AsyncClient
) -> None:
    """The card is private again on coming back: the member decides afresh."""
    ines = await client_for(await make_account())
    created = await create_org(ines)
    org_id, code = created["org"]["id"], created["org"]["access_code"]
    cami = await client_for(await make_account())
    joined = await cami.post(
        "/api/join",
        json={"code": code, "pseudo": "Cami", "avatar": AVATAR, "charter_accepted": True},
    )
    assert joined.status_code == 201, joined.text
    token = (await make_public(cami, org_id, True))["card_token"]

    assert (await leave(cami, org_id)).status_code == 204
    assert (await client.get(public_url(token))).status_code == 404

    back = await cami.post(
        "/api/join",
        json={"code": code, "pseudo": "Cami", "avatar": AVATAR, "charter_accepted": True},
    )
    assert back.status_code == 201, back.text
    assert (back.json()["membership"]["card_public"], back.json()["membership"]["card_token"]) == (
        False,
        token,
    )
    assert (await client.get(public_url(token))).status_code == 404
    assert (await make_public(cami, org_id, True))["card_token"] == token
    assert (await client.get(public_url(token))).status_code == 200


async def test_a_deleted_account_has_no_public_card(
    make_org: MakeOrg, person: MakePerson, client: httpx.AsyncClient
) -> None:
    org = await make_org()
    await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    token = (await make_public(cami.client, org.id, True))["card_token"]
    assert (await delete_me(cami.client)).status_code == 204
    assert (await client.get(public_url(token))).status_code == 404


async def test_public_cards_are_rate_limited_per_address(
    make_org: MakeOrg, person: MakePerson
) -> None:
    from sibylle.main import create_app

    org = await make_org()
    cami = await person(org, "reader", "Cami")
    token = (await make_public(cami.client, org.id, True))["card_token"]
    app = create_app()
    app.state.limits.public_card = RateLimiter(3, app.state.limits.public_card.window)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://testserver"
    ) as visitor:
        for _ in range(3):
            assert (await visitor.get(public_url(token))).status_code == 200
        blocked = await visitor.get(public_url(token))
        assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"
