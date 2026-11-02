import pytest

from sybille.services.security import hash_password, new_token, token_hash, verify_password

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
