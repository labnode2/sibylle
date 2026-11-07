"""A request's transaction is committed before its response leaves: what a client does right
after a response (here, using the session the way back from Keycloak just opened) sees the
request's writes."""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from tests.keycloak_fake import FakeKeycloak

pytestmark = pytest.mark.integration


async def test_a_new_session_works_as_soon_as_the_sign_in_answers(
    live_server: str, fake_keycloak: FakeKeycloak
) -> None:
    # Two clients, so the second request does not wait behind the first on one connection. The
    # cookies are passed by hand: they are `Secure`, and the server listens in plain http.
    async with (
        httpx.AsyncClient(base_url=f"http://{live_server}") as client,
        httpx.AsyncClient(base_url=f"http://{live_server}") as other,
    ):
        for i in range(30):
            user = fake_keycloak.add_user(f"tout-de-suite-{i}@example.test")
            started = await client.get("/api/auth/login")
            assert started.status_code == 303, started.text
            location = started.headers["location"]
            code = fake_keycloak.authorize(location, user)
            state = parse_qs(urlsplit(location).query)["state"][0]
            signin = started.cookies.get("sibylle_signin")
            back = await client.get(
                "/api/auth/callback",
                params={"code": code, "state": state},
                headers={"Cookie": f"sibylle_signin={signin}"},
            )
            assert back.status_code == 303 and back.headers["location"] == "/", back.text
            token = back.cookies.get("sibylle_session")
            me = await other.get("/api/me", headers={"Cookie": f"sibylle_session={token}"})
            assert me.status_code == 200, f"sign-in {i}: the session was not committed yet"
