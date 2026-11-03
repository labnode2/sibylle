import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pywebpush import webpush

from sibylle.cli import gen_secrets

pytestmark = pytest.mark.unit


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_fresh_secrets_each_time() -> None:
    first, second = gen_secrets(), gen_secrets()
    assert first.keys() == {"POSTGRES_PASSWORD", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"}
    assert all(first[name] != second[name] for name in first)
    assert len(first["POSTGRES_PASSWORD"]) >= 40
    # An uncompressed P-256 point, as `pushManager.subscribe` wants it.
    public = base64.urlsafe_b64decode(first["VAPID_PUBLIC_KEY"] + "=")
    assert len(public) == 65 and public[0] == 4


def test_pywebpush_signs_with_the_private_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prepared without being sent (`curl=True`): the key is read and the message encrypted."""
    monkeypatch.chdir(tmp_path)  # the curl mode writes the encrypted body to ./encrypted.data
    secrets = gen_secrets()
    device = ec.generate_private_key(ec.SECP256R1()).public_key()
    request = webpush(
        subscription_info={
            "endpoint": "https://fcm.googleapis.com/fcm/send/appareil",
            "keys": {
                "p256dh": _b64(device.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)),
                "auth": _b64(b"0123456789abcdef"),
            },
        },
        data='{"title": "Sibylle"}',
        vapid_private_key=secrets["VAPID_PRIVATE_KEY"],
        vapid_claims={"sub": "mailto:contact@exemple.fr"},
        curl=True,
    )
    assert isinstance(request, str)
    assert f"k={secrets['VAPID_PUBLIC_KEY']}" in request
