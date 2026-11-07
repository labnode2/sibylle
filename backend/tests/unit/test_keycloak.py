"""services/keycloak.py against the fake Keycloak (tests/keycloak_fake.py): the address the
browser is sent to, what the server accepts from Keycloak, and how it holds when Keycloak does
not answer (specs/002-keycloak-auth/research.md K2 to K5)."""

import time
import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from tests.keycloak_fake import CLIENT_ID, ISSUER, FakeKeycloak, Signer, challenge_of

from sibylle.config import Settings, get_settings
from sibylle.services import keycloak
from sibylle.services.keycloak import IdentityUnavailable, Rejected

pytestmark = pytest.mark.unit

NONCE = "nonce-du-test"


def query_of(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def code_for(fake: FakeKeycloak, user: str, **changes: Any) -> tuple[str, str]:
    """A code Keycloak gives back for `user`, and the PKCE verifier the server drew for it."""
    verifier, challenge = keycloak.new_pkce()
    location = keycloak.authorization_url(
        "login", state="etat", nonce=NONCE, code_challenge=challenge
    )
    return fake.authorize(location, user, **changes), verifier


async def identity_of(fake: FakeKeycloak, user: str, **changes: Any) -> keycloak.Identity:
    code, verifier = code_for(fake, user, **changes)
    return await keycloak.verify_id_token(await keycloak.exchange_code(code, verifier), NONCE)


# The browser's way there


@pytest.mark.parametrize(
    ("action", "extra"),
    [
        ("login", {}),
        ("signup", {"prompt": "create"}),
        ("password", {"kc_action": "UPDATE_PASSWORD"}),
    ],
)
def test_the_browser_goes_to_the_public_address(
    action: keycloak.Action, extra: dict[str, str]
) -> None:
    url = keycloak.authorization_url(action, state="etat", nonce=NONCE, code_challenge="defi")
    assert url.startswith(f"{ISSUER}/protocol/openid-connect/auth?")
    assert query_of(url) == {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid",
        "redirect_uri": f"{get_settings().public_origin}/api/auth/callback",
        "state": "etat",
        "nonce": NONCE,
        "code_challenge": "defi",
        "code_challenge_method": "S256",
        **extra,
    }


def test_the_forgotten_password_page_needs_no_attempt() -> None:
    url = keycloak.forgot_password_url()
    assert url == f"{ISSUER}/login-actions/reset-credentials?client_id={CLIENT_ID}"


def test_pkce_verifiers_are_long_random_and_s256() -> None:
    pairs = [keycloak.new_pkce() for _ in range(20)]
    assert len({verifier for verifier, _ in pairs}) == 20
    for verifier, challenge in pairs:
        assert 43 <= len(verifier) <= 128
        assert all(c.isalnum() or c in "-._~" for c in verifier)
        assert challenge == challenge_of(verifier)


# The identity token


async def test_a_code_gives_the_persons_identity(fake_keycloak: FakeKeycloak) -> None:
    user = fake_keycloak.add_user("Cami@Exemple.fr", first_name="Camille", verified=False)
    identity = await identity_of(fake_keycloak, user)
    assert identity == keycloak.Identity(
        sub=uuid.UUID(user),
        sid=fake_keycloak.sid_of(user),
        email="cami@exemple.fr",
        email_verified=False,
        first_name="Camille",
        last_name="Martin",
    )
    # The code, the keys: every call went to the internal address (the fake checks it).
    assert fake_keycloak.calls_to("/protocol/openid-connect/token")
    assert fake_keycloak.calls_to("/protocol/openid-connect/certs")


async def test_names_may_be_missing(fake_keycloak: FakeKeycloak) -> None:
    user = fake_keycloak.add_user("sacha@exemple.fr", first_name="Sacha", last_name=None)
    identity = await identity_of(fake_keycloak, user)
    assert (identity.first_name, identity.last_name) == ("Sacha", "")


async def test_a_code_serves_once_and_with_its_verifier(fake_keycloak: FakeKeycloak) -> None:
    user = fake_keycloak.add_user("leo@exemple.fr")
    code, verifier = code_for(fake_keycloak, user)
    with pytest.raises(Rejected):
        await keycloak.exchange_code(code, verifier + "x")
    code, verifier = code_for(fake_keycloak, user)
    await keycloak.exchange_code(code, verifier)
    with pytest.raises(Rejected):
        await keycloak.exchange_code(code, verifier)


@pytest.mark.parametrize(
    ("changes", "signed_with"),
    [
        ({"iss": "https://ailleurs.test/realms/sibylle"}, "realm"),
        ({"aud": "une-autre-appli", "azp": "une-autre-appli"}, "realm"),
        ({"nonce": "un-autre-nonce"}, "realm"),
        ({"nonce": None}, "realm"),
        ({"iat": int(time.time()) - 600, "exp": int(time.time()) - 120}, "realm"),
        ({"sub": "pas-un-identifiant"}, "realm"),
        ({"email": None}, "realm"),
        ({}, "stranger"),
        ({}, "encryption"),
        ({}, "none"),
        ({}, "hs256"),
    ],
    ids=[
        "other-issuer",
        "other-audience",
        "other-nonce",
        "no-nonce",
        "expired",
        "sub-not-an-id",
        "no-email",
        "unknown-key",
        "encryption-key",
        "alg-none",
        "alg-hs256",
    ],
)
async def test_an_identity_token_that_does_not_hold_is_refused(
    fake_keycloak: FakeKeycloak, changes: dict[str, Any], signed_with: Signer
) -> None:
    user = fake_keycloak.add_user("manon@exemple.fr")
    with pytest.raises(Rejected):
        await identity_of(fake_keycloak, user, signed_with=signed_with, **changes)


async def test_an_unknown_key_reloads_the_keys_once(
    fake_keycloak: FakeKeycloak, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = fake_keycloak.add_user("ines@exemple.fr")
    await identity_of(fake_keycloak, user)
    assert len(fake_keycloak.calls_to("/certs")) == 1
    await identity_of(fake_keycloak, user)
    assert len(fake_keycloak.calls_to("/certs")) == 1  # kept

    # Keycloak signs with a new key: the server fetches the keys again, once.
    monkeypatch.setattr(keycloak, "KEYS_RELOAD_AFTER", 0)
    fake_keycloak.rotate_keys()
    await identity_of(fake_keycloak, user)
    assert len(fake_keycloak.calls_to("/certs")) == 2
    with pytest.raises(Rejected):
        await identity_of(fake_keycloak, user, signed_with="stranger")
    assert len(fake_keycloak.calls_to("/certs")) == 3

    # A run of tokens with unknown keys does not make it fetch them at each one.
    monkeypatch.setattr(keycloak, "KEYS_RELOAD_AFTER", 10)
    with pytest.raises(Rejected):
        await identity_of(fake_keycloak, user, signed_with="stranger")
    assert len(fake_keycloak.calls_to("/certs")) == 3


# The back-channel logout token


async def test_a_logout_token_names_a_session_or_an_account(fake_keycloak: FakeKeycloak) -> None:
    user = fake_keycloak.add_user("hugo@exemple.fr")
    by_session = await keycloak.verify_logout_token(fake_keycloak.logout_token(sid="session-1"))
    assert by_session == keycloak.Logout(sid="session-1", sub=None)
    by_account = await keycloak.verify_logout_token(fake_keycloak.logout_token(sub=user))
    assert by_account == keycloak.Logout(sid=None, sub=uuid.UUID(user))


@pytest.mark.parametrize(
    ("changes", "signed_with"),
    [
        ({"events": {}}, "realm"),
        ({"events": None}, "realm"),
        ({"sid": None, "sub": None}, "realm"),
        ({"nonce": "un-nonce"}, "realm"),
        ({"iat": int(time.time()) - 301}, "realm"),
        ({"iat": None}, "realm"),
        ({"aud": "une-autre-appli"}, "realm"),
        ({"iss": "https://ailleurs.test/realms/sibylle"}, "realm"),
        ({}, "stranger"),
        ({}, "none"),
    ],
    ids=[
        "no-event",
        "no-events",
        "no-sid-nor-sub",
        "nonce",
        "too-old",
        "no-iat",
        "other-audience",
        "other-issuer",
        "unknown-key",
        "alg-none",
    ],
)
async def test_a_logout_token_that_does_not_hold_is_refused(
    fake_keycloak: FakeKeycloak, changes: dict[str, Any], signed_with: Signer
) -> None:
    changes = {"sid": "session-1", **changes}
    with pytest.raises(Rejected):
        await keycloak.verify_logout_token(
            fake_keycloak.logout_token(signed_with=signed_with, **changes)
        )


async def test_an_unreadable_token_is_refused() -> None:
    for token in ("", "pas.un.jeton", "abc"):
        with pytest.raises(Rejected):
            await keycloak.verify_logout_token(token)


# The admin API, with the client's service account


async def test_the_admin_calls(fake_keycloak: FakeKeycloak) -> None:
    user = fake_keycloak.add_user("zoe@exemple.fr", verified=False)
    found = await keycloak.get_user(uuid.UUID(user))
    assert found is not None and found["email"] == "zoe@exemple.fr"
    assert await keycloak.get_user(uuid.uuid4()) is None

    await keycloak.send_verify_email(
        uuid.UUID(user), "https://sibylle.test/api/auth/login?suite=/compte"
    )
    [sent] = fake_keycloak.calls_to("/send-verify-email")
    assert sent.startswith(f"PUT /admin/realms/sibylle/users/{user}/send-verify-email?")
    assert query_of(sent.split(" ", 1)[1]) == {
        "client_id": CLIENT_ID,
        "redirect_uri": "https://sibylle.test/api/auth/login?suite=/compte",
    }

    code, verifier = code_for(fake_keycloak, user)
    await keycloak.exchange_code(code, verifier)
    sid = fake_keycloak.sid_of(user)
    await keycloak.delete_session(sid)
    assert sid not in fake_keycloak.sessions
    await keycloak.delete_session(sid)  # already closed: nothing to do

    await keycloak.delete_user(uuid.UUID(user))
    assert user not in fake_keycloak.users
    await keycloak.delete_user(uuid.UUID(user))  # already gone: counts as deleted


async def test_the_service_accounts_token_is_kept_until_shortly_before_it_expires(
    fake_keycloak: FakeKeycloak,
) -> None:
    user = uuid.UUID(fake_keycloak.add_user("paul@exemple.fr"))
    for _ in range(3):
        await keycloak.get_user(user)
    assert len(fake_keycloak.calls_to("/token")) == 1

    # A token about to expire is not used: each call takes a new one.
    keycloak.forget()
    fake_keycloak.token_lifetime = 20
    await keycloak.get_user(user)
    await keycloak.get_user(user)
    assert len(fake_keycloak.calls_to("/token")) == 3

    # A token Keycloak no longer takes (restarted, say) is replaced once.
    fake_keycloak.token_lifetime = 300
    await keycloak.get_user(user)
    fake_keycloak._tokens.clear()
    assert await keycloak.get_user(user) is not None
    assert len(fake_keycloak.calls_to("/token")) == 5


async def test_a_refused_service_account_is_an_unavailable_keycloak(
    fake_keycloak: FakeKeycloak, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "plus-le-bon")
    get_settings.cache_clear()
    try:
        with pytest.raises(IdentityUnavailable):
            await keycloak.get_user(uuid.uuid4())
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


# When Keycloak does not answer


async def test_a_stopped_keycloak_is_unavailable(fake_keycloak: FakeKeycloak) -> None:
    fake_keycloak.down = True
    assert await keycloak.realm_is_up() is False
    with pytest.raises(IdentityUnavailable):
        await keycloak.get_user(uuid.uuid4())
    with pytest.raises(IdentityUnavailable):
        await keycloak.exchange_code("code", "verificateur")
    with pytest.raises(IdentityUnavailable):
        await keycloak.verify_logout_token(fake_keycloak.logout_token(sid="session-1"))


async def test_a_call_without_answer_in_time_is_unavailable(
    fake_keycloak: FakeKeycloak, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await keycloak.realm_is_up() is True
    monkeypatch.setattr(keycloak, "TIMEOUT", 0.05)
    monkeypatch.setattr(keycloak, "UP_TIMEOUT", 0.05)
    fake_keycloak.delay = 1.0
    started = time.monotonic()
    with pytest.raises(IdentityUnavailable):
        await keycloak.delete_user(uuid.uuid4())
    assert await keycloak.realm_is_up() is False
    assert time.monotonic() - started < 0.9


# The settings


def test_the_server_calls_keycloak_on_its_internal_address() -> None:
    settings = Settings(
        _env_file=None,
        oidc_issuer="https://auth.sibylle.cc/realms/sibylle/",
        keycloak_internal_url="http://keycloak:8080",
    )
    assert settings.oidc_issuer == "https://auth.sibylle.cc/realms/sibylle"
    assert settings.keycloak_realm_url == "http://keycloak:8080/realms/sibylle"
    alone = Settings(
        _env_file=None, oidc_issuer="http://localhost:8280/realms/sibylle", keycloak_internal_url=""
    )
    assert alone.keycloak_realm_url == "http://localhost:8280/realms/sibylle"


@pytest.mark.parametrize(
    ("changes", "refused"),
    [
        ({"oidc_client_secret": ""}, "OIDC_CLIENT_SECRET"),
        ({"oidc_issuer": "http://localhost:8280/realms/sibylle"}, "OIDC_ISSUER"),
        ({}, None),
    ],
)
def test_production_needs_its_client_secret_and_https(
    changes: dict[str, str], refused: str | None
) -> None:
    settings = {
        "environment": "production",
        "oidc_issuer": "https://auth.sibylle.cc/realms/sibylle",
        "oidc_client_secret": "un-secret",
        **changes,
    }
    if refused is None:
        Settings(_env_file=None, **settings)  # type: ignore[arg-type]
        return
    with pytest.raises(ValueError, match=refused):
        Settings(_env_file=None, **settings)  # type: ignore[arg-type]
