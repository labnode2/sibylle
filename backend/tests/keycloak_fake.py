"""A Keycloak in memory for the tests (specs/002-keycloak-auth/research.md K12).

It serves, behind an `httpx.MockTransport`, what `services/keycloak.py` calls on the internal
address: the realm's keys, its token endpoint (authorization code with PKCE, and the client's own
credentials) and the few admin calls of the service account. The browser's part of a sign-in, the
pages where a person types their password, is played by `authorize`, which turns the address the
server sent the browser to into a code. The keys are RSA keys made for the tests; tokens are
signed the way Keycloak signs them, and dated with the real time, as Keycloak dates them.
"""

import asyncio
import base64
import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

# The realm's public address, which the tokens carry, and the address of the server's own calls,
# as in production (OIDC_ISSUER and KEYCLOAK_INTERNAL_URL).
ISSUER = "https://auth.sibylle.test/realms/sibylle"
INTERNAL = "http://keycloak:8080"
CLIENT_ID = "sibylle"
CLIENT_SECRET = "secret-de-test"
LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"

_REALM = "/realms/sibylle"
_ADMIN = "/admin/realms/sibylle"

Signer = Literal["realm", "stranger", "encryption", "none", "hs256"]


def _rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


# Made once per test run: an RSA key takes a moment.
_SIGNING_KEYS = [_rsa_key(), _rsa_key()]
_ENCRYPTION_KEY = _rsa_key()  # the realm's other key, for encryption only: never a signature's
_STRANGER_KEY = _rsa_key()  # a key the realm does not have


def _jwk(kid: str, key: rsa.RSAPrivateKey, use: str, alg: str) -> dict[str, Any]:
    public: dict[str, Any] = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {**public, "kid": kid, "use": use, "alg": alg}


def challenge_of(verifier: str) -> str:
    """The PKCE `S256` challenge of a verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@dataclass
class _Code:
    client_id: str
    redirect_uri: str
    challenge: str
    id_token: str
    used: bool = False


@dataclass
class FakeKeycloak:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Keycloak's sessions: sid -> user id
    sessions: dict[str, str] = field(default_factory=dict)
    # Every request received, as "METHOD /path?query"
    calls: list[str] = field(default_factory=list)
    # True: every request fails as if Keycloak were stopped (httpx.ConnectError); `unreachable`:
    # only the requests whose path holds one of these fragments.
    down: bool = False
    unreachable: tuple[str, ...] = ()
    # Seconds before each answer, to try the server's time limits.
    delay: float = 0.0
    # Lifetime of the service account's tokens, in seconds (`expires_in`).
    token_lifetime: int = 300
    _key_index: int = 0
    _codes: dict[str, _Code] = field(default_factory=dict)
    _tokens: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.transport = httpx.MockTransport(self._handle)

    # The realm's people and sessions

    def add_user(
        self,
        email: str,
        *,
        first_name: str | None = "Camille",
        last_name: str | None = "Martin",
        verified: bool = True,
        enabled: bool = True,
        user_id: uuid.UUID | str | None = None,
    ) -> str:
        """Creates an account in the realm, as the sign-up page does; returns its id."""
        user = str(user_id or uuid.uuid4())
        self.users[user] = {
            "id": user,
            "username": email.lower(),
            "email": email.lower(),
            "emailVerified": verified,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": enabled,
        }
        return user

    def calls_to(self, fragment: str) -> list[str]:
        return [call for call in self.calls if fragment in call]

    # The browser's side

    def authorize(
        self,
        location: str,
        user: str,
        *,
        signed_with: Signer = "realm",
        **changes: Any,
    ) -> str:
        """The code Keycloak sends the browser back with, once `user` has signed in on its pages
        from `location`, the address the server redirected to. The identity token it will give
        for the code carries the person's claims, changed by `changes` (`nonce=`, `aud=`, `iss=`,
        `exp=`…); a change to None removes the claim."""
        url = urlsplit(location)
        assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/protocol/openid-connect/auth"
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        assert query["response_type"] == "code" and query["code_challenge_method"] == "S256"
        assert "openid" in query["scope"].split()
        person = self.users[user]
        sid = str(uuid.uuid4())
        self.sessions[sid] = user
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": query["client_id"],
            "azp": query["client_id"],
            "sub": user,
            "sid": sid,
            "typ": "ID",
            "iat": now,
            "exp": now + 300,
            "nonce": query.get("nonce"),
            "email": person["email"],
            "email_verified": person["emailVerified"],
            "given_name": person["firstName"],
            "family_name": person["lastName"],
        }
        claims.update(changes)
        claims = {key: value for key, value in claims.items() if value is not None}
        code = secrets.token_urlsafe(24)
        self._codes[code] = _Code(
            client_id=query["client_id"],
            redirect_uri=query["redirect_uri"],
            challenge=query["code_challenge"],
            id_token=self.sign(claims, signed_with),
        )
        return code

    def sid_of(self, user: str) -> str:
        """The id of the user's latest Keycloak session."""
        return [sid for sid, owner in self.sessions.items() if owner == user][-1]

    # Tokens

    @property
    def kid(self) -> str:
        return f"cle-{self._key_index + 1}"

    def rotate_keys(self) -> None:
        """Signs with a new key from now on, and serves only that one."""
        self._key_index = (self._key_index + 1) % len(_SIGNING_KEYS)

    def sign(self, claims: dict[str, Any], signed_with: Signer = "realm") -> str:
        if signed_with == "none":
            return jwt.encode(claims, None, algorithm="none")
        if signed_with == "hs256":
            # The classic forgery: a shared secret instead of the realm's key.
            return jwt.encode(claims, CLIENT_SECRET.ljust(32, "-"), algorithm="HS256")
        key, kid = {
            "realm": (_SIGNING_KEYS[self._key_index], self.kid),
            "stranger": (_STRANGER_KEY, "cle-inconnue"),
            "encryption": (_ENCRYPTION_KEY, "cle-chiffrement"),
        }[signed_with]
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})

    def logout_token(
        self,
        *,
        sid: str | None = None,
        sub: str | None = None,
        signed_with: Signer = "realm",
        **changes: Any,
    ) -> str:
        """A back-channel logout token for a Keycloak session (`sid`) or a whole account (`sub`),
        as Keycloak sends it; `changes` alter its claims (`events=`, `nonce=`, `iat=`, `aud=`…)."""
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
            "typ": "Logout",
            "sid": sid,
            "sub": sub,
            "events": {LOGOUT_EVENT: {}},
        }
        claims.update(changes)
        claims = {key: value for key, value in claims.items() if value is not None}
        return self.sign(claims, signed_with)

    # The server's side

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.raw_path.decode()}")
        if self.down or any(part in request.url.path for part in self.unreachable):
            raise httpx.ConnectError("Keycloak is stopped", request=request)
        if self.delay:
            await asyncio.sleep(self.delay)
        assert f"{request.url.scheme}://{request.url.netloc.decode()}" == INTERNAL, (
            f"the server called Keycloak on {request.url}, not on its internal address"
        )
        path = request.url.path
        if request.method == "GET" and path == _REALM:
            return httpx.Response(200, json={"realm": "sibylle"})
        if request.method == "GET" and path == f"{_REALM}/protocol/openid-connect/certs":
            return httpx.Response(200, json={"keys": self._keys()})
        if request.method == "POST" and path == f"{_REALM}/protocol/openid-connect/token":
            return self._token(parse_qs(request.content.decode()))
        if path.startswith(_ADMIN + "/"):
            return self._admin(request, path.removeprefix(_ADMIN))
        return httpx.Response(404, json={"error": "Unable to find matching target resource"})

    def _keys(self) -> list[dict[str, Any]]:
        return [
            _jwk(self.kid, _SIGNING_KEYS[self._key_index], "sig", "RS256"),
            _jwk("cle-chiffrement", _ENCRYPTION_KEY, "enc", "RSA-OAEP"),
        ]

    def _token(self, form: dict[str, list[str]]) -> httpx.Response:
        values = {key: value[0] for key, value in form.items()}
        if (values.get("client_id"), values.get("client_secret")) != (CLIENT_ID, CLIENT_SECRET):
            return httpx.Response(401, json={"error": "unauthorized_client"})
        if values.get("grant_type") == "client_credentials":
            token = secrets.token_urlsafe(24)
            self._tokens[token] = time.time() + self.token_lifetime
            return httpx.Response(
                200,
                json={
                    "access_token": token,
                    "expires_in": self.token_lifetime,
                    "token_type": "Bearer",
                },
            )
        if values.get("grant_type") != "authorization_code":
            return httpx.Response(400, json={"error": "unsupported_grant_type"})
        code = self._codes.get(values.get("code", ""))
        if (
            code is None
            or code.used
            or code.client_id != CLIENT_ID
            or code.redirect_uri != values.get("redirect_uri")
            or code.challenge != challenge_of(values.get("code_verifier", ""))
        ):
            return httpx.Response(400, json={"error": "invalid_grant"})
        code.used = True
        return httpx.Response(
            200,
            json={
                "access_token": secrets.token_urlsafe(24),
                "id_token": code.id_token,
                "expires_in": 300,
                "token_type": "Bearer",
            },
        )

    def _admin(self, request: httpx.Request, path: str) -> httpx.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if self._tokens.get(token, 0) <= time.time():
            return httpx.Response(401, json={"error": "HTTP 401 Unauthorized"})
        parts = path.strip("/").split("/")
        if parts[0] == "sessions" and len(parts) == 2 and request.method == "DELETE":
            if self.sessions.pop(parts[1], None) is None:
                return httpx.Response(404, json={"error": "Sesssion not found"})
            return httpx.Response(204)
        if parts[0] != "users" or len(parts) not in (2, 3):
            return httpx.Response(404, json={"error": "Unable to find matching target resource"})
        user = self.users.get(parts[1])
        if user is None:
            return httpx.Response(404, json={"error": "User not found"})
        if len(parts) == 3 and parts[2] == "send-verify-email" and request.method == "PUT":
            return httpx.Response(204)
        if len(parts) == 2 and request.method == "GET":
            return httpx.Response(200, json=user)
        if len(parts) == 2 and request.method == "DELETE":
            del self.users[parts[1]]
            for sid in [sid for sid, owner in self.sessions.items() if owner == parts[1]]:
                del self.sessions[sid]
            return httpx.Response(204)
        return httpx.Response(405)
