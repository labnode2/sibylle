"""Signing up and in through Keycloak (specs/002-keycloak-auth/contracts/auth.md), against the
fake Keycloak of tests/keycloak_fake.py: the way to Keycloak's pages, the way back, and the
account it opens."""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import func, select
from tests.conftest import ORIGIN, ClientFor, MakeAccount
from tests.contract.helpers import SIGNIN_COOKIE, sign_in, start_sign_in
from tests.keycloak_fake import CLIENT_ID, ISSUER, FakeKeycloak

from sibylle import clock
from sibylle.db.models import Account, AuthSession, SignInAttempt
from sibylle.db.session import transaction
from sibylle.services.security import token_hash

pytestmark = pytest.mark.contract


def query_of(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def set_cookies(response: httpx.Response) -> dict[str, str]:
    """Each cookie the response sets, by name, with its attributes in lower case."""
    found = {}
    for header in response.headers.get_list("set-cookie"):
        name = header.split("=", 1)[0]
        found[name] = header.lower()
    return found


async def attempts() -> list[SignInAttempt]:
    async with transaction() as session:
        return list((await session.scalars(select(SignInAttempt))).all())


async def accounts_count() -> int:
    async with transaction() as session:
        return int(await session.scalar(select(func.count()).select_from(Account)) or 0)


# The way to Keycloak


async def test_login_sends_the_browser_to_keycloak(client: httpx.AsyncClient) -> None:
    response = await start_sign_in(client, suite="/rejoindre/abc?x=1")
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"{ISSUER}/protocol/openid-connect/auth?")
    query = query_of(location)
    assert query["client_id"] == CLIENT_ID
    assert (query["response_type"], query["scope"]) == ("code", "openid")
    assert query["redirect_uri"] == f"{ORIGIN}/api/auth/callback"
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) == 43
    assert len(query["state"]) >= 32 and len(query["nonce"]) >= 32
    assert "prompt" not in query and "kc_action" not in query

    cookie = set_cookies(response)[SIGNIN_COOKIE]
    for attribute in ("httponly", "secure", "samesite=lax", "path=/api/auth", "max-age=600"):
        assert attribute in cookie, cookie
    [attempt] = await attempts()
    assert (attempt.action, attempt.next_path) == ("login", "/rejoindre/abc?x=1")
    assert (attempt.state, attempt.nonce) == (query["state"], query["nonce"])
    assert attempt.code_verifier not in location
    lifetime = attempt.expires_at - attempt.created_at
    assert timedelta(minutes=10) - timedelta(seconds=1) < lifetime <= timedelta(minutes=10)


async def test_signup_opens_the_sign_up_page(client: httpx.AsyncClient) -> None:
    response = await start_sign_in(client, action="signup", suite="/rejoindre/abc")
    assert query_of(response.headers["location"])["prompt"] == "create"
    [attempt] = await attempts()
    assert attempt.action == "signup"


@pytest.mark.parametrize(
    "suite",
    ["//exemple.org", "/\\exemple.org", "https://exemple.org", "exemple.org", "", "/\nexemple"],
)
async def test_the_way_back_stays_in_sibylle(client: httpx.AsyncClient, suite: str) -> None:
    response = await start_sign_in(client, suite=suite)
    assert response.status_code == 303
    [attempt] = await attempts()
    assert attempt.next_path == "/"


async def test_without_keycloak_the_sign_in_waits(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    fake_keycloak.down = True
    for action in ("login", "signup", "forgot"):
        response = await start_sign_in(client, action=action, suite="/compte")
        assert response.status_code == 303
        assert response.headers["location"] == "/connexion-indisponible?suite=%2Fcompte"
        assert SIGNIN_COOKIE not in set_cookies(response)
    assert await attempts() == []


async def test_a_forgotten_password_goes_straight_to_keycloaks_page(
    client: httpx.AsyncClient,
) -> None:
    response = await start_sign_in(client, action="forgot")
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"{ISSUER}/login-actions/reset-credentials?client_id={CLIENT_ID}"
    )
    assert SIGNIN_COOKIE not in set_cookies(response)
    assert await attempts() == []


async def test_an_unknown_action_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/login", params={"action": "tout"})
    assert response.status_code == 422


# The way back


async def test_a_first_sign_in_creates_the_account(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    # Keycloak's sign-up page made the account; the person comes back with a code.
    user = fake_keycloak.add_user(
        "Cami@Exemple.fr", first_name="Camille", last_name="Martin", verified=False
    )
    response = await sign_in(client, fake_keycloak, user, suite="/rejoindre/abc")
    assert response.status_code == 303
    assert response.headers["location"] == "/rejoindre/abc"
    cookies = set_cookies(response)
    session_cookie = cookies["sibylle_session"]
    for attribute in ("httponly", "secure", "samesite=lax", "path=/;"):
        assert attribute in session_cookie + ";", session_cookie
    assert 'sibylle_signin=""' in cookies[SIGNIN_COOKIE] or "max-age=0" in cookies[SIGNIN_COOKIE]
    assert await attempts() == []

    me = (await client.get("/api/me")).json()
    assert me["email"] == "cami@exemple.fr"
    assert (me["first_name"], me["last_name"], me["email_verified"]) == ("Camille", "Martin", False)
    assert me["memberships"] == []
    async with transaction() as session:
        account = await session.get(Account, uuid.UUID(me["id"]))
        assert account is not None and account.keycloak_id == uuid.UUID(user)
        auth = await session.scalar(select(AuthSession).where(AuthSession.account_id == account.id))
        assert auth is not None and auth.keycloak_sid == fake_keycloak.sid_of(user)


async def test_a_known_account_is_taken_up_and_copied_again(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak, make_account: MakeAccount
) -> None:
    account = await make_account("hugo@exemple.fr", first_name="Hugo", verified=False)
    assert account.keycloak_id is not None
    user = fake_keycloak.users[str(account.keycloak_id)]
    user.update(email="hugo.b@exemple.fr", firstName="Hugues", lastName="Bernard")
    user["emailVerified"] = True

    response = await sign_in(client, fake_keycloak, str(account.keycloak_id))
    assert response.headers["location"] == "/"
    me = (await client.get("/api/me")).json()
    assert me["id"] == str(account.id)
    assert (me["email"], me["first_name"], me["last_name"]) == (
        "hugo.b@exemple.fr",
        "Hugues",
        "Bernard",
    )
    assert me["email_verified"] is True
    assert await accounts_count() == 1

    # Keycloak says the address is not confirmed any more (a new address, say).
    user["emailVerified"] = False
    await sign_in(client, fake_keycloak, str(account.keycloak_id))
    assert (await client.get("/api/me")).json()["email_verified"] is False


async def test_an_address_of_another_account_stops_the_sign_in(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak, make_account: MakeAccount
) -> None:
    # A Sibylle account holds the address, tied to another Keycloak account: never tied by the
    # address (research.md K6).
    await make_account("leo@exemple.fr")
    newcomer = fake_keycloak.add_user("LEO@exemple.fr")
    response = await sign_in(client, fake_keycloak, newcomer, suite="/compte")
    assert response.status_code == 303
    assert response.headers["location"] == "/connexion?erreur=email_taken&suite=%2Fcompte"
    assert "sibylle_session" not in set_cookies(response)
    assert await accounts_count() == 1
    assert (await client.get("/api/me")).status_code == 401


async def test_a_deleted_accounts_address_is_free(
    client: httpx.AsyncClient,
    fake_keycloak: FakeKeycloak,
    make_account: MakeAccount,
    client_for: ClientFor,
) -> None:
    gone = await make_account("manon@exemple.fr")
    signed_in = await client_for(gone)
    assert (await signed_in.request("DELETE", "/api/me", json={"confirm": True})).status_code == 204
    again = fake_keycloak.add_user("manon@exemple.fr")
    response = await sign_in(client, fake_keycloak, again)
    assert response.headers["location"] == "/"
    me = (await client.get("/api/me")).json()
    assert me["id"] != str(gone.id) and me["email"] == "manon@exemple.fr"


async def sign_in_failure(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak, **changes: object
) -> httpx.Response:
    user = fake_keycloak.add_user(f"essai-{uuid.uuid4().hex[:6]}@exemple.fr")
    return await sign_in(client, fake_keycloak, user, suite="/compte", **changes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"signed_with": "stranger"},
        {"aud": "une-autre-appli", "azp": "une-autre-appli"},
        {"nonce": "un-autre-nonce"},
    ],
    ids=["bad-signature", "other-audience", "other-nonce"],
)
async def test_an_identity_token_that_does_not_hold_signs_nobody_in(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak, changes: dict[str, object]
) -> None:
    response = await sign_in_failure(client, fake_keycloak, **changes)
    assert response.headers["location"] == "/connexion?erreur=failed&suite=%2Fcompte"
    assert "sibylle_session" not in set_cookies(response)
    assert await accounts_count() == 0
    assert await attempts() == []


async def test_a_return_without_its_attempt_is_expired(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak, fake_clock: clock.FakeClock
) -> None:
    user = fake_keycloak.add_user("zoe@exemple.fr")

    # No cookie: another browser came back (or someone sent a link).
    started = await start_sign_in(client, suite="/compte")
    code = fake_keycloak.authorize(started.headers["location"], user)
    state = query_of(started.headers["location"])["state"]
    client.cookies.clear()
    lost = await client.get("/api/auth/callback", params={"code": code, "state": state})
    assert lost.headers["location"] == "/connexion?erreur=expired"

    # Another state than the attempt's.
    started = await start_sign_in(client, suite="/compte")
    code = fake_keycloak.authorize(started.headers["location"], user)
    other = await client.get("/api/auth/callback", params={"code": code, "state": "autre"})
    assert other.headers["location"] == "/connexion?erreur=expired&suite=%2Fcompte"

    # An attempt older than 10 minutes.
    started = await start_sign_in(client)
    code = fake_keycloak.authorize(started.headers["location"], user)
    state = query_of(started.headers["location"])["state"]
    fake_clock.advance(timedelta(minutes=10, seconds=1))
    late = await client.get("/api/auth/callback", params={"code": code, "state": state})
    assert late.headers["location"] == "/connexion?erreur=expired"

    # An attempt already served.
    started = await start_sign_in(client)
    cookie = client.cookies.get(SIGNIN_COOKIE)
    code = fake_keycloak.authorize(started.headers["location"], user)
    state = query_of(started.headers["location"])["state"]
    first = await client.get("/api/auth/callback", params={"code": code, "state": state})
    assert first.headers["location"] == "/"
    assert cookie is not None
    client.cookies.set(SIGNIN_COOKIE, cookie, path="/api/auth")
    again = await client.get("/api/auth/callback", params={"code": code, "state": state})
    assert again.headers["location"] == "/connexion?erreur=expired"
    assert await accounts_count() == 1


async def test_a_sign_in_cancelled_on_keycloaks_page(client: httpx.AsyncClient) -> None:
    started = await start_sign_in(client, suite="/compte")
    state = query_of(started.headers["location"])["state"]
    response = await client.get(
        "/api/auth/callback", params={"error": "access_denied", "state": state}
    )
    assert response.headers["location"] == "/connexion?erreur=denied&suite=%2Fcompte"
    assert await attempts() == []
    other = await start_sign_in(client)
    state = query_of(other.headers["location"])["state"]
    failed = await client.get(
        "/api/auth/callback", params={"error": "temporarily_unavailable", "state": state}
    )
    assert failed.headers["location"] == "/connexion?erreur=failed"


async def test_without_keycloak_at_the_exchange_the_sign_in_waits(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    user = fake_keycloak.add_user("yanis@exemple.fr")
    started = await start_sign_in(client, suite="/compte")
    code = fake_keycloak.authorize(started.headers["location"], user)
    state = query_of(started.headers["location"])["state"]
    fake_keycloak.down = True
    response = await client.get("/api/auth/callback", params={"code": code, "state": state})
    assert response.headers["location"] == "/connexion-indisponible?suite=%2Fcompte"
    assert "sibylle_session" not in set_cookies(response)
    assert await accounts_count() == 0


async def test_a_return_without_code_nor_error_fails(client: httpx.AsyncClient) -> None:
    started = await start_sign_in(client)
    state = query_of(started.headers["location"])["state"]
    response = await client.get("/api/auth/callback", params={"state": state})
    assert response.headers["location"] == "/connexion?erreur=failed"


# The address check (US2, research.md K9): Keycloak sends it, Sibylle asks for it


async def test_a_new_unconfirmed_account_gets_the_address_check(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    user = fake_keycloak.add_user("lou@exemple.fr", verified=False)
    response = await sign_in(client, fake_keycloak, user)
    assert response.headers["location"] == "/"
    [sent] = fake_keycloak.calls_to("/send-verify-email")
    assert sent.startswith(f"PUT /admin/realms/sibylle/users/{user}/send-verify-email?")
    assert query_of(sent.split(" ", 1)[1]) == {
        "client_id": CLIENT_ID,
        "redirect_uri": f"{ORIGIN}/api/auth/login?suite=/compte",
    }
    # Signing in again sends nothing more: the settings send it again on demand.
    await sign_in(client, fake_keycloak, user)
    assert len(fake_keycloak.calls_to("/send-verify-email")) == 1


async def test_a_confirmed_address_gets_no_check(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    user = fake_keycloak.add_user("noe@exemple.fr", verified=True)
    await sign_in(client, fake_keycloak, user)
    assert fake_keycloak.calls_to("/send-verify-email") == []


async def test_a_check_keycloak_does_not_send_stops_nobody(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    fake_keycloak.unreachable = ("/send-verify-email",)
    user = fake_keycloak.add_user("eli@exemple.fr", verified=False)
    response = await sign_in(client, fake_keycloak, user)
    assert response.headers["location"] == "/"
    assert (await client.get("/api/me")).json()["email_verified"] is False


async def test_the_check_is_sent_again_three_times_an_hour(
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_keycloak: FakeKeycloak,
    fake_clock: clock.FakeClock,
) -> None:
    account = await make_account(verified=False)
    signed_in = await client_for(account)
    for _ in range(3):
        assert (await signed_in.post("/api/auth/verify-email/resend")).status_code == 204
    sent = fake_keycloak.calls_to(f"/users/{account.keycloak_id}/send-verify-email")
    assert len(sent) == 3
    blocked = await signed_in.post("/api/auth/verify-email/resend")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert len(fake_keycloak.calls_to("/send-verify-email")) == 3
    fake_clock.advance(timedelta(hours=1))
    assert (await signed_in.post("/api/auth/verify-email/resend")).status_code == 204
    assert len(fake_keycloak.calls_to("/send-verify-email")) == 4


async def test_a_confirmed_address_is_not_checked_again(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    signed_in = await client_for(await make_account(verified=True))
    assert (await signed_in.post("/api/auth/verify-email/resend")).status_code == 204
    assert fake_keycloak.calls_to("/send-verify-email") == []


async def test_without_keycloak_the_check_waits(
    make_account: MakeAccount, client_for: ClientFor, fake_keycloak: FakeKeycloak
) -> None:
    signed_in = await client_for(await make_account(verified=False))
    fake_keycloak.down = True
    response = await signed_in.post("/api/auth/verify-email/resend")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identity_unavailable"


# A new password (US3, research.md K10)


async def test_a_new_password_is_asked_of_keycloak(client: httpx.AsyncClient) -> None:
    response = await start_sign_in(client, action="password", suite="/compte")
    query = query_of(response.headers["location"])
    assert query["kc_action"] == "UPDATE_PASSWORD"
    assert "prompt" not in query
    [attempt] = await attempts()
    assert (attempt.action, attempt.next_path) == ("password", "/compte")


async def test_the_way_back_replaces_the_browsers_session(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    user = fake_keycloak.add_user("gael@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    before = client.cookies.get("sibylle_session")
    response = await sign_in(client, fake_keycloak, user, action="password", suite="/compte")
    assert response.headers["location"] == "/compte"
    after = client.cookies.get("sibylle_session")
    assert after is not None and after != before
    async with transaction() as session:
        left = (await session.scalars(select(AuthSession.token_hash))).all()
    assert left == [token_hash(after)]
    assert (await client.get("/api/me")).status_code == 200


# Sessions closed by Keycloak (US4, research.md K8 and K15)


@asynccontextmanager
async def another_browser() -> AsyncIterator[httpx.AsyncClient]:
    from sibylle.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="https://testserver",
        headers={"X-Sibylle": "1", "Origin": ORIGIN},
    ) as browser:
        yield browser


async def from_keycloak(logout_token: str) -> httpx.Response:
    """A back-channel logout as Keycloak sends it: a form, without X-Sibylle nor Origin."""
    from sibylle.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://sibylle:8443"
    ) as keycloak_side:
        return await keycloak_side.post(
            "/api/auth/backchannel-logout", data={"logout_token": logout_token}
        )


async def test_keycloak_closes_one_session(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    user = fake_keycloak.add_user("rose@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    first = fake_keycloak.sid_of(user)
    async with another_browser() as phone:
        await sign_in(phone, fake_keycloak, user)
        response = await from_keycloak(fake_keycloak.logout_token(sid=first, sub=user))
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert (await client.get("/api/me")).status_code == 401
        assert (await phone.get("/api/me")).status_code == 200


async def test_keycloak_closes_every_session_of_an_account(
    client: httpx.AsyncClient,
    fake_keycloak: FakeKeycloak,
    make_account: MakeAccount,
    client_for: ClientFor,
) -> None:
    user = fake_keycloak.add_user("max@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    someone_else = await client_for(await make_account())
    async with another_browser() as phone:
        await sign_in(phone, fake_keycloak, user)
        response = await from_keycloak(fake_keycloak.logout_token(sub=user))
        assert response.status_code == 200
        assert (await client.get("/api/me")).status_code == 401
        assert (await phone.get("/api/me")).status_code == 401
    assert (await someone_else.get("/api/me")).status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"signed_with": "stranger"},
        {"aud": "une-autre-appli"},
        {"events": {}},
        {"nonce": "un-nonce"},
        {"iat": "too-old"},
    ],
    ids=["bad-signature", "other-audience", "no-event", "nonce", "too-old"],
)
async def test_a_logout_token_that_does_not_hold_closes_nothing(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak, changes: dict[str, Any]
) -> None:
    user = fake_keycloak.add_user("ines@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    if changes.get("iat") == "too-old":
        changes = {"iat": int(time.time()) - 301}
    token = fake_keycloak.logout_token(sid=fake_keycloak.sid_of(user), **changes)
    response = await from_keycloak(token)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_token"
    assert (await client.get("/api/me")).status_code == 200


async def test_a_logout_without_a_token_is_refused(client: httpx.AsyncClient) -> None:
    from sibylle.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://sibylle:8443"
    ) as keycloak_side:
        assert (await keycloak_side.post("/api/auth/backchannel-logout")).status_code == 422
        assert (await keycloak_side.get("/api/auth/backchannel-logout")).status_code == 405


async def test_without_keycloaks_keys_a_logout_waits(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    token = fake_keycloak.logout_token(sid="une-session")
    fake_keycloak.down = True
    response = await from_keycloak(token)
    assert response.status_code == 503


async def account_sessions(account_id: uuid.UUID) -> int:
    async with transaction() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.account_id == account_id)
        )
    return int(count or 0)


@pytest.mark.parametrize("gone", ["disabled", "deleted"])
async def test_an_account_gone_from_keycloak_is_signed_out_within_the_hour(
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_keycloak: FakeKeycloak,
    fake_clock: clock.FakeClock,
    gone: str,
) -> None:
    account = await make_account()
    here = await client_for(account)
    elsewhere = await client_for(account)
    someone_else = await client_for(await make_account())
    if gone == "disabled":
        fake_keycloak.users[str(account.keycloak_id)]["enabled"] = False
    else:
        del fake_keycloak.users[str(account.keycloak_id)]

    # Within the hour of its last prolongation, a session asks nothing of Keycloak.
    fake_clock.advance(timedelta(minutes=59))
    assert (await here.get("/api/me")).status_code == 200
    assert fake_keycloak.calls_to(f"/users/{account.keycloak_id}") == []

    # Past it, Keycloak's answer signs the account out, everywhere.
    fake_clock.advance(timedelta(minutes=2))
    response = await here.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert await account_sessions(account.id) == 0
    assert (await elsewhere.get("/api/me")).status_code == 401
    assert (await someone_else.get("/api/me")).status_code == 200


async def test_an_account_still_in_keycloak_goes_on(
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_keycloak: FakeKeycloak,
    fake_clock: clock.FakeClock,
) -> None:
    account = await make_account()
    here = await client_for(account)
    reads = f"GET /admin/realms/sibylle/users/{account.keycloak_id}"
    fake_clock.advance(timedelta(hours=2))
    assert (await here.get("/api/me")).status_code == 200
    assert len(fake_keycloak.calls_to(reads)) == 1
    # Prolonged: the next read is an hour away.
    fake_clock.advance(timedelta(minutes=30))
    assert (await here.get("/api/me")).status_code == 200
    assert len(fake_keycloak.calls_to(reads)) == 1


async def test_without_keycloak_a_session_goes_on(
    make_account: MakeAccount,
    client_for: ClientFor,
    fake_keycloak: FakeKeycloak,
    fake_clock: clock.FakeClock,
) -> None:
    account = await make_account()
    here = await client_for(account)
    fake_keycloak.down = True
    fake_clock.advance(timedelta(hours=2))
    assert (await here.get("/api/me")).status_code == 200
    async with transaction() as session:
        auth = await session.scalar(select(AuthSession).where(AuthSession.account_id == account.id))
        assert auth is not None and auth.last_seen_at > clock.now() - timedelta(minutes=1)


# Sign-out, the account's own settings, the routes that went


async def test_sign_out(client: httpx.AsyncClient, fake_keycloak: FakeKeycloak) -> None:
    user = fake_keycloak.add_user("paul@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    sid = fake_keycloak.sid_of(user)
    assert (await client.get("/api/me")).status_code == 200
    response = await client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "sibylle_session" in set_cookies(response)
    assert (await client.get("/api/me")).status_code == 401
    # Keycloak's session closes too, or Keycloak would sign the browser in again at once.
    assert sid not in fake_keycloak.sessions
    assert fake_keycloak.calls_to(f"DELETE /admin/realms/sibylle/sessions/{sid}")


async def test_sign_out_without_keycloak(
    client: httpx.AsyncClient, fake_keycloak: FakeKeycloak
) -> None:
    user = fake_keycloak.add_user("ana@exemple.fr")
    await sign_in(client, fake_keycloak, user)
    fake_keycloak.down = True
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/me")).status_code == 401


async def test_update_me(make_account: MakeAccount, client_for: ClientFor) -> None:
    account = await make_account()
    signed_in = await client_for(account)
    assert (await signed_in.get("/api/me")).json()["theme"] == "light"
    response = await signed_in.patch(
        "/api/me", json={"theme": "dark", "reduce_motion": True, "first_name": "Cami"}
    )
    assert response.status_code == 200
    me = response.json()
    assert (me["theme"], me["reduce_motion"]) == ("dark", True)
    # The names come from Keycloak: they change there, not here.
    assert me["first_name"] == "Camille"
    assert (await signed_in.patch("/api/me", json={"theme": "sepia"})).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/signup",
        "/api/auth/login",
        "/api/auth/verify-email",
        "/api/auth/password-reset",
        "/api/auth/password-reset/confirm",
        "/api/me/password",
    ],
)
async def test_the_old_sign_in_routes_are_gone(
    make_account: MakeAccount, client_for: ClientFor, path: str
) -> None:
    signed_in = await client_for(await make_account())
    response = await signed_in.post(path, json={"email": "x@exemple.fr", "password": "x"})
    assert response.status_code in (404, 405)


@pytest.mark.parametrize(
    "headers",
    [{"X-Sibylle": "", "Origin": ORIGIN}, {"X-Sibylle": "1", "Origin": "https://ailleurs.example"}],
)
async def test_changes_need_the_header_and_the_origin(
    make_account: MakeAccount, client_for: ClientFor, headers: dict[str, str]
) -> None:
    signed_in = await client_for(await make_account())
    response = await signed_in.post("/api/auth/logout", headers=headers)
    assert response.status_code == 403
    assert (await signed_in.get("/api/me")).status_code == 200
