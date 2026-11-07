"""Keycloak, which runs sign-up, sign-in, passwords and address checks for Sibylle
(specs/002-keycloak-auth, research.md K1 to K9).

The browser is only ever sent to the realm's public address, `OIDC_ISSUER`. The server's own
calls (the code exchange, the realm's keys, the admin API) go to the realm's internal address
(`Settings.keycloak_realm_url`, `http://keycloak:8080` in production), each within TIMEOUT
seconds; `IdentityUnavailable` says Keycloak did not answer. The admin calls use the client's
service account (`manage-users`, with the `kc-admin-api` scope that Keycloak 26.8 wants, K5).

Tokens are checked against the real time, as Keycloak dates them, never against the game's
clock, which the tests and the demo move.
"""

import asyncio
import base64
import hashlib
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt

from sibylle.config import get_settings

log = logging.getLogger(__name__)

Action = Literal["login", "signup", "password"]

# Seconds: each call to Keycloak; the check before sending a browser there (FR-017).
TIMEOUT = 3.0
UP_TIMEOUT = 2.0
# Seconds of difference allowed between Keycloak's clock and this machine's.
LEEWAY = 30
LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"
# A back-channel logout token older than this is refused (contracts/auth.md).
LOGOUT_TOKEN_MAX_AGE = 300
# An unknown key fetches the realm's keys again, at most this often (seconds): Keycloak may have
# a new key, but a run of forged tokens must not make the server ask for them at each one.
KEYS_RELOAD_AFTER = 10.0
# The service account's token is renewed this long before it expires (seconds).
TOKEN_MARGIN = 30.0
# Seconds for Keycloak to send an e-mail: it answers once its mail server has taken it.
SEND_TIMEOUT = 10.0


class IdentityUnavailable(Exception):
    """Keycloak did not answer in time, or failed."""


class Rejected(Exception):
    """Keycloak refused the code, or a token does not hold."""


@dataclass(frozen=True)
class Identity:
    """The person an identity token speaks of, and the Keycloak session it opened."""

    sub: uuid.UUID
    sid: str | None
    email: str
    email_verified: bool
    first_name: str
    last_name: str


@dataclass(frozen=True)
class Logout:
    """What a back-channel logout closes: one Keycloak session, or every session of an account."""

    sid: str | None
    sub: uuid.UUID | None


@dataclass
class _Kept:
    """The realm's keys and the service account's token, kept between calls."""

    transport: httpx.AsyncBaseTransport | None = None
    keys: dict[str, Any] | None = None
    keys_loaded_at: float = 0.0
    token: str | None = None
    token_expires_at: float = 0.0


_kept = _Kept()


def use_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Sends every call to Keycloak through `transport` (the tests' fake Keycloak), or through
    the network with None, and forgets the keys and the token kept so far."""
    _kept.transport = transport
    forget()


def forget() -> None:
    """Drops the keys and the token kept so far."""
    _kept.keys, _kept.keys_loaded_at = None, 0.0
    _kept.token, _kept.token_expires_at = None, 0.0


# The browser's way there


def callback_url() -> str:
    return f"{get_settings().public_origin}/api/auth/callback"


def new_pkce() -> tuple[str, str]:
    """A PKCE verifier, kept by the server, and its `S256` challenge, sent along the browser."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def authorization_url(action: Action, *, state: str, nonce: str, code_challenge: str) -> str:
    """Keycloak's sign-in page, on the public address: the sign-up page for `signup`, and a new
    password to choose, after signing in if need be, for `password` (research.md K10)."""
    settings = get_settings()
    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "scope": "openid",
        "redirect_uri": callback_url(),
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if action == "signup":
        params["prompt"] = "create"
    elif action == "password":
        params["kc_action"] = "UPDATE_PASSWORD"
    return f"{settings.oidc_issuer}/protocol/openid-connect/auth?{urlencode(params)}"


def forgot_password_url() -> str:
    """Keycloak's « Mot de passe oublié » page, which needs no sign-in under way (K10)."""
    settings = get_settings()
    query = urlencode({"client_id": settings.oidc_client_id})
    return f"{settings.oidc_issuer}/login-actions/reset-credentials?{query}"


# Calls to Keycloak


async def _request(
    method: str, url: str, *, within: float | None = None, **kwargs: Any
) -> httpx.Response:
    """One call to Keycloak's internal address. IdentityUnavailable when it does not answer
    within the time limit, or answers with a server error."""
    limit = TIMEOUT if within is None else within
    try:
        async with asyncio.timeout(limit):
            async with httpx.AsyncClient(transport=_kept.transport, timeout=limit) as client:
                response = await client.request(method, url, **kwargs)
    except (httpx.HTTPError, TimeoutError) as error:
        log.warning("keycloak did not answer", extra={"url": url, "error": repr(error)})
        raise IdentityUnavailable(url) from error
    if response.status_code >= 500:
        log.warning("keycloak failed", extra={"url": url, "status": response.status_code})
        raise IdentityUnavailable(url)
    return response


def _realm_url() -> str:
    return get_settings().keycloak_realm_url


def _admin_url() -> str:
    head, _, realm = _realm_url().rpartition("/realms/")
    return f"{head}/admin/realms/{realm}"


async def realm_is_up() -> bool:
    """The realm answers within UP_TIMEOUT seconds."""
    try:
        response = await _request("GET", _realm_url(), within=UP_TIMEOUT)
    except IdentityUnavailable:
        return False
    return response.status_code == 200


async def exchange_code(code: str, code_verifier: str) -> str:
    """The identity token for the code Keycloak sent the browser back with."""
    settings = get_settings()
    response = await _request(
        "POST",
        f"{_realm_url()}/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url(),
            "code_verifier": code_verifier,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        },
    )
    if response.status_code != 200:
        log.warning(
            "keycloak refused the code",
            extra={"status": response.status_code, "error": _error_of(response)},
        )
        raise Rejected("code refused")
    id_token = response.json().get("id_token")
    if not isinstance(id_token, str):
        raise Rejected("no identity token")
    return id_token


def _error_of(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    return str(error) if error is not None else None


# Tokens


async def _load_keys() -> dict[str, Any]:
    response = await _request("GET", f"{_realm_url()}/protocol/openid-connect/certs")
    if response.status_code != 200:
        log.warning("keycloak's keys could not be read", extra={"status": response.status_code})
        raise IdentityUnavailable("keys")
    keys: dict[str, Any] = {}
    for jwk in response.json().get("keys", []):
        # Signature keys only: the realm also has an encryption key.
        if (
            jwk.get("kty") != "RSA"
            or jwk.get("use", "sig") != "sig"
            or jwk.get("alg", "RS256") != "RS256"
            or not jwk.get("kid")
        ):
            continue
        keys[jwk["kid"]] = jwt.PyJWK(jwk, algorithm="RS256").key
    _kept.keys, _kept.keys_loaded_at = keys, time.monotonic()
    return keys


async def _signing_key(kid: str | None) -> Any:
    keys = _kept.keys
    if keys is None:
        keys = await _load_keys()
    elif kid not in keys and time.monotonic() - _kept.keys_loaded_at >= KEYS_RELOAD_AFTER:
        keys = await _load_keys()
    key = keys.get(kid) if kid else None
    if key is None:
        raise Rejected("unknown key")
    return key


async def _verify(token: str, required: list[str]) -> dict[str, Any]:
    """The claims of a token the realm signed for this client."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise Rejected("unreadable token") from error
    if header.get("alg") != "RS256":
        raise Rejected(f"algorithm {header.get('alg')!r}")
    key = await _signing_key(header.get("kid"))
    settings = get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer,
            leeway=LEEWAY,
            options={"require": ["iss", "aud", "iat", *required]},
        )
    except jwt.PyJWTError as error:
        raise Rejected(str(error)) from error
    return claims


def _uuid(value: Any) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as error:
        raise Rejected("not an account id") from error


async def verify_id_token(token: str, nonce: str) -> Identity:
    """The person signed in, from the identity token of the code exchange: signed by the realm,
    for this client, still valid, and for this sign-in (its nonce)."""
    claims = await _verify(token, ["exp", "sub"])
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise Rejected("nonce")
    email = claims.get("email")
    if not isinstance(email, str) or not email:
        raise Rejected("no e-mail")
    sid = claims.get("sid")
    return Identity(
        sub=_uuid(claims["sub"]),
        sid=str(sid) if sid else None,
        email=email.strip().lower(),
        email_verified=claims.get("email_verified") is True,
        first_name=str(claims.get("given_name") or ""),
        last_name=str(claims.get("family_name") or ""),
    )


async def verify_logout_token(token: str) -> Logout:
    """What a back-channel logout token closes (OpenID Connect Back-Channel Logout 1.0): signed
    by the realm, for this client, recent, with the logout event, and never an identity token."""
    claims = await _verify(token, [])
    events = claims.get("events")
    if not isinstance(events, dict) or LOGOUT_EVENT not in events:
        raise Rejected("not a logout")
    if "nonce" in claims:
        raise Rejected("a nonce")
    if time.time() - float(claims["iat"]) > LOGOUT_TOKEN_MAX_AGE:
        raise Rejected("too old")
    sid, sub = claims.get("sid"), claims.get("sub")
    if not sid and not sub:
        raise Rejected("no session nor account")
    return Logout(sid=str(sid) if sid else None, sub=_uuid(sub) if sub else None)


# The admin API, as the client's service account


async def _service_token(*, renew: bool = False) -> str:
    now = time.monotonic()
    if not renew and _kept.token and now < _kept.token_expires_at - TOKEN_MARGIN:
        return _kept.token
    settings = get_settings()
    response = await _request(
        "POST",
        f"{_realm_url()}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        },
    )
    if response.status_code != 200:
        log.error(
            "keycloak refused the service account",
            extra={"status": response.status_code, "error": _error_of(response)},
        )
        raise IdentityUnavailable("service account")
    body = response.json()
    _kept.token = str(body["access_token"])
    _kept.token_expires_at = now + float(body.get("expires_in", 60))
    return _kept.token


async def _admin(method: str, path: str, *ok: int, **kwargs: Any) -> httpx.Response:
    """A call to the realm's admin API, answered with one of the `ok` statuses; a token that no
    longer holds is renewed once."""
    url = f"{_admin_url()}{path}"
    response = None
    for renew in (False, True):
        token = await _service_token(renew=renew)
        headers = {"Authorization": f"Bearer {token}"}
        response = await _request(method, url, headers=headers, **kwargs)
        if response.status_code != 401:
            break
    assert response is not None
    if response.status_code not in ok:
        log.error(
            "keycloak's admin API refused a call",
            extra={"method": method, "path": path, "status": response.status_code},
        )
        raise IdentityUnavailable(path)
    return response


async def get_user(user_id: uuid.UUID) -> dict[str, Any] | None:
    """The account in the realm, or None once it is gone."""
    response = await _admin("GET", f"/users/{user_id}", 200, 404)
    if response.status_code == 404:
        return None
    user: dict[str, Any] = response.json()
    return user


async def delete_user(user_id: uuid.UUID) -> None:
    """Deletes the account in the realm; one already gone counts as deleted."""
    await _admin("DELETE", f"/users/{user_id}", 204, 404)


async def send_verify_email(user_id: uuid.UUID, redirect_uri: str) -> None:
    """Has Keycloak send the address check, whose link ends on `redirect_uri` (research.md K9)."""
    params = {"client_id": get_settings().oidc_client_id, "redirect_uri": redirect_uri}
    await _admin(
        "PUT", f"/users/{user_id}/send-verify-email", 204, params=params, within=SEND_TIMEOUT
    )


async def delete_session(sid: str) -> None:
    """Closes a Keycloak session; one already closed counts as closed (research.md K7)."""
    await _admin("DELETE", f"/sessions/{sid}", 204, 404)
