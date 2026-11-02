from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from tests.conftest import ORIGIN, PASSWORD, ClientFor, MakeAccount
from tests.contract.helpers import notifications, token_from

from sibylle import clock
from sibylle.db.models import Account
from sibylle.db.session import transaction

pytestmark = pytest.mark.contract

SIGNUP = {
    "email": "Cami@Exemple.fr",
    "password": "boule-de-cristal",
    "first_name": "Camille",
    "last_name": "Martin",
}


async def signup(client: httpx.AsyncClient, **changes: str) -> httpx.Response:
    return await client.post("/api/auth/signup", json={**SIGNUP, **changes})


async def test_signup_signs_in_and_queues_the_address_check(client: httpx.AsyncClient) -> None:
    response = await signup(client)
    assert response.status_code == 201
    me = response.json()
    assert me["email"] == "cami@exemple.fr"
    assert (me["first_name"], me["last_name"]) == ("Camille", "Martin")
    assert me["email_verified"] is False
    assert me["memberships"] == []
    cookie = response.headers["set-cookie"].lower()
    assert "sibylle_session=" in cookie
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie

    assert (await client.get("/api/me")).json()["id"] == me["id"]
    [queued] = await notifications("verify_email")
    assert "jeton=" in queued.payload["link"]


async def test_signup_refuses_a_taken_address_whatever_its_case(
    client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    await make_account("cami@exemple.fr")
    response = await signup(client, email="CAMI@exemple.fr")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("field", "value"),
    [("password", "court"), ("email", "pas-une-adresse"), ("first_name", ""), ("last_name", "")],
)
async def test_signup_validates_its_fields(
    client: httpx.AsyncClient, field: str, value: str
) -> None:
    response = await signup(client, **{field: value})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert field in error["fields"]


async def test_login_and_logout(client: httpx.AsyncClient, make_account: MakeAccount) -> None:
    await make_account("hugo@exemple.fr")
    wrong = await client.post(
        "/api/auth/login", json={"email": "hugo@exemple.fr", "password": "mauvais-mot"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"
    unknown = await client.post(
        "/api/auth/login", json={"email": "personne@exemple.fr", "password": PASSWORD}
    )
    assert unknown.json()["error"]["code"] == "invalid_credentials"

    ok = await client.post(
        "/api/auth/login", json={"email": "HUGO@exemple.fr", "password": PASSWORD}
    )
    assert ok.status_code == 200
    assert ok.json()["email"] == "hugo@exemple.fr"
    assert (await client.get("/api/me")).status_code == 200

    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/me")).status_code == 401


async def test_login_is_rate_limited(client: httpx.AsyncClient, make_account: MakeAccount) -> None:
    await make_account("leo@exemple.fr")
    for _ in range(10):
        response = await client.post(
            "/api/auth/login", json={"email": "leo@exemple.fr", "password": "mauvais-mot"}
        )
        assert response.status_code == 401
    blocked = await client.post(
        "/api/auth/login", json={"email": "leo@exemple.fr", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


async def test_update_me(make_account: MakeAccount, client_for: ClientFor) -> None:
    account = await make_account()
    signed_in = await client_for(account)
    response = await signed_in.patch(
        "/api/me", json={"theme": "dark", "reduce_motion": True, "first_name": "Cami"}
    )
    assert response.status_code == 200
    me = response.json()
    assert (me["theme"], me["reduce_motion"], me["first_name"]) == ("dark", True, "Cami")
    assert (await signed_in.patch("/api/me", json={"theme": "sepia"})).status_code == 422


async def test_change_password_closes_the_other_sessions(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    account = await make_account()
    here = await client_for(account)
    elsewhere = await client_for(account)
    wrong = await here.post(
        "/api/me/password", json={"current_password": "pas-le-bon", "new_password": "nouveau-mot"}
    )
    assert wrong.status_code == 422
    assert "current_password" in wrong.json()["error"]["fields"]
    response = await here.post(
        "/api/me/password", json={"current_password": PASSWORD, "new_password": "nouveau-mot"}
    )
    assert response.status_code == 204
    assert (await here.get("/api/me")).status_code == 200
    assert (await elsewhere.get("/api/me")).status_code == 401


async def test_verify_email_with_a_single_use_link(
    client: httpx.AsyncClient, fake_clock: clock.FakeClock
) -> None:
    await signup(client)
    [queued] = await notifications("verify_email")
    token = token_from(queued.payload["link"])
    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 204
    assert (await client.get("/api/me")).json()["email_verified"] is True
    again = await client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "token_invalid"


async def test_a_verification_link_expires_after_24_hours(
    client: httpx.AsyncClient, fake_clock: clock.FakeClock
) -> None:
    await signup(client)
    assert (await client.post("/api/auth/verify-email/resend")).status_code == 204
    queued = await notifications("verify_email")
    assert len(queued) == 2
    fake_clock.advance(timedelta(hours=24, minutes=1))
    expired = await client.post(
        "/api/auth/verify-email", json={"token": token_from(queued[-1].payload["link"])}
    )
    assert expired.json()["error"]["code"] == "token_invalid"


async def test_password_reset(
    client: httpx.AsyncClient,
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_clock: clock.FakeClock,
) -> None:
    account = await make_account("manon@exemple.fr")
    signed_in = await client_for(account)

    unknown = await client.post("/api/auth/password-reset", json={"email": "x@exemple.fr"})
    assert unknown.status_code == 202
    assert await notifications("reset_password") == []

    known = await client.post("/api/auth/password-reset", json={"email": "manon@exemple.fr"})
    assert known.status_code == 202
    [queued] = await notifications("reset_password")
    token = token_from(queued.payload["link"])

    confirm = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "tout-nouveau"}
    )
    assert confirm.status_code == 204
    assert (await signed_in.get("/api/me")).status_code == 401
    login = await client.post(
        "/api/auth/login", json={"email": "manon@exemple.fr", "password": "tout-nouveau"}
    )
    assert login.status_code == 200
    reuse = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "encore-autre"}
    )
    assert reuse.json()["error"]["code"] == "token_invalid"


async def test_a_reset_link_expires_after_one_hour(
    client: httpx.AsyncClient, make_account: MakeAccount, fake_clock: clock.FakeClock
) -> None:
    await make_account("yanis@exemple.fr")
    await client.post("/api/auth/password-reset", json={"email": "yanis@exemple.fr"})
    [queued] = await notifications("reset_password")
    fake_clock.advance(timedelta(hours=1, minutes=1))
    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token_from(queued.payload["link"]), "password": "tout-nouveau"},
    )
    assert response.json()["error"]["code"] == "token_invalid"
    async with transaction() as session:
        stored = await session.scalar(select(Account).where(Account.email == "yanis@exemple.fr"))
        assert stored is not None and stored.password_hash is not None


@pytest.mark.parametrize(
    "headers",
    [{"X-Sibylle": "", "Origin": ORIGIN}, {"X-Sibylle": "1", "Origin": "https://ailleurs.example"}],
)
async def test_changes_need_the_header_and_the_origin(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post("/api/auth/signup", json=SIGNUP, headers=headers)
    assert response.status_code == 403
