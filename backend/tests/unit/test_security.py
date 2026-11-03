import pytest

from sibylle.config import Settings
from sibylle.services.security import hash_password, new_token, token_hash, verify_password

pytestmark = pytest.mark.unit


def test_password_hash_is_argon2id_and_verifies() -> None:
    hashed = hash_password("lauriers et boules")
    assert hashed.startswith("$argon2id$")
    assert "lauriers" not in hashed
    assert verify_password(hashed, "lauriers et boules")
    assert not verify_password(hashed, "lauriers et boule")


def test_same_password_hashes_differently() -> None:
    assert hash_password("même mot") != hash_password("même mot")


def test_verify_rejects_a_malformed_hash() -> None:
    assert not verify_password("pas-un-hash", "x")


def test_tokens_are_long_random_and_url_safe() -> None:
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100
    for token in tokens:
        assert len(token) >= 43
        assert all(c.isalnum() or c in "-_" for c in token)


def test_only_the_token_hash_is_stored() -> None:
    token = new_token()
    digest = token_hash(token)
    assert digest == token_hash(token)
    assert digest != token
    assert len(digest) == 64
    assert digest != token_hash(new_token())


@pytest.mark.parametrize(
    ("environment", "origin", "secure"),
    [
        ("development", "http://localhost:5173", True),
        ("development", "http://127.0.0.1:5173", True),
        ("development", "https://sibylle.test", True),
        # The app tried on a phone, from the PC's address on the local network.
        ("development", "http://192.168.71.12:5173", False),
        ("test", "http://192.168.71.12:5180", False),
        # Production keeps it whatever the address.
        ("production", "http://192.168.71.12:5173", True),
        ("production", "https://sibylle.exemple.fr", True),
    ],
)
def test_the_session_cookie_is_secure_but_on_a_local_network_in_http(
    environment: str, origin: str, secure: bool
) -> None:
    settings = Settings(_env_file=None, environment=environment, public_origin=origin)
    assert settings.secure_cookies is secure
