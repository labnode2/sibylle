"""A session that Keycloak closes closes its WebSocket too, with 4401 (contracts/auth.md,
« Jeton de déconnexion back-channel », and contracts/realtime.md of the v1); the other sessions'
stay open."""

import asyncio
from typing import Any

import httpx
import pytest
import websockets
from tests.conftest import ORIGIN, ClientFor, MakeOrg, MakePerson
from tests.contract.helpers import sign_in
from tests.keycloak_fake import FakeKeycloak

pytestmark = pytest.mark.integration


async def connect(server: str, token: str | None) -> Any:
    return await websockets.connect(
        f"ws://{server}/api/ws",
        origin=ORIGIN,  # type: ignore[arg-type]
        additional_headers={"Cookie": f"sibylle_session={token}"},
    )


async def test_a_session_keycloak_closes_closes_its_websocket(
    live_server: str, client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    from sibylle.main import create_app

    user = fake_keycloak.add_user("lena@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    laptop_sid = fake_keycloak.sid_of(user)
    laptop = await connect(live_server, client.cookies.get("sibylle_session"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="https://testserver",
        headers={"X-Sibylle": "1", "Origin": ORIGIN},
    ) as other:
        await sign_in(other, fake_keycloak, user)
        phone = await connect(live_server, other.cookies.get("sibylle_session"))

    async with httpx.AsyncClient(base_url=f"http://{live_server}") as keycloak_side:
        closed = await keycloak_side.post(
            "/api/auth/backchannel-logout",
            data={"logout_token": fake_keycloak.logout_token(sid=laptop_sid, sub=user)},
        )
    assert closed.status_code == 200

    await asyncio.wait_for(laptop.wait_closed(), timeout=5)
    assert laptop.close_code == 4401
    # The phone's session is another Keycloak session: its WebSocket stays.
    await asyncio.sleep(0.3)
    assert phone.close_code is None
    await phone.close()


async def test_deleting_my_account_closes_my_other_devices(
    live_server: str, make_org: MakeOrg, person: MakePerson, client_for: ClientFor
) -> None:
    org = await make_org()
    await person(org, "editor", "Inès")
    cami = await person(org, "reader", "Cami")
    other_device = await client_for(cami.account)
    laptop = await connect(live_server, cami.client.cookies.get("sibylle_session"))
    phone = await connect(live_server, other_device.cookies.get("sibylle_session"))

    deleted = await cami.client.request("DELETE", "/api/me", json={"confirm": True})
    assert deleted.status_code == 204, deleted.text

    await asyncio.wait_for(phone.wait_closed(), timeout=5)
    assert phone.close_code == 4401
    # The browser that deleted the account closes its own, on its way to the goodbye page.
    await asyncio.sleep(0.3)
    assert laptop.close_code is None
    await laptop.close()
