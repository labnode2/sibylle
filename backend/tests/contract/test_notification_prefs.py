import httpx
import pytest
from sqlalchemy import select
from tests.conftest import ClientFor, MakeAccount

from sibylle.config import get_settings
from sibylle.db.models import PushSubscription
from sibylle.db.session import transaction

pytestmark = pytest.mark.contract

TYPES = ["new_prono", "closing_soon", "result", "designation_reminder"]
DEVICE = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/telephone-de-cami",
    "keys": {"p256dh": "cle-publique", "auth": "secret"},
}


async def test_eight_switches_all_on_by_default(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    cami = await client_for(await make_account())
    prefs = (await cami.get("/api/me/notification-prefs")).json()
    assert prefs == [
        {"type": type, "channel": channel, "enabled": True}
        for type in TYPES
        for channel in ("push", "email")
    ]

    response = await cami.put(
        "/api/me/notification-prefs",
        json=[
            {"type": "closing_soon", "channel": "email", "enabled": False},
            {"type": "result", "channel": "push", "enabled": False},
        ],
    )
    assert response.status_code == 200, response.text
    off = {(p["type"], p["channel"]) for p in response.json() if not p["enabled"]}
    assert off == {("closing_soon", "email"), ("result", "push")}

    again = await cami.put(
        "/api/me/notification-prefs",
        json=[{"type": "closing_soon", "channel": "email", "enabled": True}],
    )
    off = {(p["type"], p["channel"]) for p in again.json() if not p["enabled"]}
    assert off == {("result", "push")}
    assert (await cami.get("/api/me/notification-prefs")).json() == again.json()


@pytest.mark.parametrize(
    "pref",
    [
        {"type": "invitation", "channel": "email", "enabled": False},
        {"type": "result", "channel": "sms", "enabled": False},
    ],
)
async def test_only_the_four_types_and_two_channels(
    make_account: MakeAccount, client_for: ClientFor, pref: dict[str, object]
) -> None:
    cami = await client_for(await make_account())
    response = await cami.put("/api/me/notification-prefs", json=[pref])
    assert response.status_code == 422


async def test_the_vapid_public_key(
    make_account: MakeAccount, client_for: ClientFor, monkeypatch: pytest.MonkeyPatch
) -> None:
    cami = await client_for(await make_account())
    monkeypatch.setattr(get_settings(), "vapid_public_key", "")
    assert (await cami.get("/api/push/vapid-public-key")).json() == {"key": None}
    monkeypatch.setattr(get_settings(), "vapid_public_key", "BCle-publique")
    assert (await cami.get("/api/push/vapid-public-key")).json() == {"key": "BCle-publique"}


async def test_a_device_subscribes_and_unsubscribes(
    make_account: MakeAccount, client_for: ClientFor
) -> None:
    cami_account = await make_account()
    cami = await client_for(cami_account)
    created = await cami.post(
        "/api/me/push-subscriptions", json=DEVICE, headers={"User-Agent": "Firefox"}
    )
    assert created.status_code == 201, created.text
    subscription_id = created.json()["id"]
    # The same device again: the same subscription.
    again = await cami.post("/api/me/push-subscriptions", json=DEVICE)
    assert again.json()["id"] == subscription_id

    # Someone else signs in on that device: the subscription follows them.
    hugo_account = await make_account()
    hugo = await client_for(hugo_account)
    moved = await hugo.post("/api/me/push-subscriptions", json=DEVICE)
    assert moved.json()["id"] == subscription_id
    async with transaction() as session:
        stored = await session.scalar(select(PushSubscription))
        assert stored is not None and stored.account_id == hugo_account.id

    assert (await cami.delete(f"/api/me/push-subscriptions/{subscription_id}")).status_code == 404
    assert (await hugo.delete(f"/api/me/push-subscriptions/{subscription_id}")).status_code == 204
    async with transaction() as session:
        assert (await session.scalars(select(PushSubscription))).all() == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/en-clair",
        "https://127.0.0.1/interne",
        "https://pirate.exemple/googleapis.com",
        "https://evilgoogleapis.com/push",
    ],
)
async def test_only_the_browsers_push_services(
    make_account: MakeAccount, client_for: ClientFor, endpoint: str
) -> None:
    """The worker posts to the endpoint: anything else would let a member aim it elsewhere."""
    cami = await client_for(await make_account())
    response = await cami.post("/api/me/push-subscriptions", json={**DEVICE, "endpoint": endpoint})
    assert response.status_code == 422
    assert "endpoint" in response.json()["error"]["fields"]


async def test_signed_out_gets_nothing(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/me/notification-prefs")).status_code == 401
    assert (await client.get("/api/push/vapid-public-key")).status_code == 401
