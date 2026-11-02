"""A request's transaction is committed before its response leaves: what a client does right
after a response (here, using the session it just got) sees the request's writes."""

import httpx
import pytest
from tests.conftest import ORIGIN

pytestmark = pytest.mark.integration


async def test_a_new_session_works_as_soon_as_signup_answers(live_server: str) -> None:
    headers = {"X-Sybille": "1", "Origin": ORIGIN}
    # Two clients, so the second request does not wait behind the first on one connection.
    async with (
        httpx.AsyncClient(base_url=f"http://{live_server}") as client,
        httpx.AsyncClient(base_url=f"http://{live_server}") as other,
    ):
        for i in range(30):
            signup = await client.post(
                "/api/auth/signup",
                json={
                    "email": f"tout-de-suite-{i}@example.test",
                    "password": "lauriers-de-test",
                    "first_name": "Zoé",
                    "last_name": "Test",
                },
                headers=headers,
            )
            assert signup.status_code == 201
            token = signup.cookies.get("sybille_session")
            me = await other.get("/api/me", headers={"Cookie": f"sybille_session={token}"})
            assert me.status_code == 200, f"signup {i}: the session was not committed yet"
