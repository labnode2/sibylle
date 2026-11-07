"""Secret tokens: the session cookie's, the sign-ins under way. Only a token's SHA-256 digest is
ever stored. Sibylle holds no password: Keycloak does (specs/002-keycloak-auth)."""

import hashlib
import secrets


def new_token() -> str:
    """256 random bits, safe in a URL or a cookie."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
