"""Small helpers shared by the contract tests."""

import asyncio
import re
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import select, text, update
from tests.keycloak_fake import FakeKeycloak

from sibylle.db.models import CoinEntry, Membership, Notification
from sibylle.db.session import transaction
from sibylle.domain.content import AVATAR_TEMPLATES

AVATAR: dict[str, Any] = AVATAR_TEMPLATES[0]["image"]
PRIVATE_KEYS = {"email", "first_name", "last_name", "keycloak_id"}
SIGNIN_COOKIE = "sibylle_signin"


async def notifications(type: str) -> list[Notification]:
    async with transaction() as session:
        return list(
            (
                await session.scalars(
                    select(Notification)
                    .where(Notification.type == type)
                    .order_by(Notification.created_at)
                )
            ).all()
        )


async def waiting_on_a_lock(task: asyncio.Task[Any]) -> None:
    """Returns once a transaction waits on a lock another one holds, or once `task` is over
    because nothing made it wait; fails after 5 seconds of neither."""
    async with asyncio.timeout(5):
        while not task.done():
            async with transaction() as session:
                waiting = await session.scalar(
                    text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'")
                )
            if waiting:
                return
            await asyncio.sleep(0.02)


async def give_coins(member: Membership, amount: int, week: date = date(2026, 10, 26)) -> None:
    """Coins as if a past Monday had converted them, for tests that only need to buy."""
    async with transaction() as session:
        session.add(
            CoinEntry(
                org_id=member.org_id,
                membership_id=member.id,
                kind="weekly",
                amount=amount,
                week_start=week,
                gold=amount,
            )
        )
        await session.execute(
            update(Membership)
            .where(Membership.id == member.id)
            .values(coins=Membership.coins + amount)
        )


def token_from(link: str) -> str:
    match = re.search(r"(?:jeton=|/rejoindre/)([A-Za-z0-9_-]+)", link)
    assert match, link
    return match.group(1)


async def create_org(
    client: httpx.AsyncClient, title: str = "Sophia Office", pseudo: str = "Inès"
) -> dict[str, Any]:
    response = await client.post(
        "/api/orgs",
        json={"title": title, "background_key": "mer", "pseudo": pseudo, "avatar": AVATAR},
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def assert_no_private_data(payload: Any) -> None:
    """No name, first name or e-mail anywhere in a payload."""
    if isinstance(payload, dict):
        assert not PRIVATE_KEYS & payload.keys(), payload
        for value in payload.values():
            assert_no_private_data(value)
    elif isinstance(payload, list):
        for value in payload:
            assert_no_private_data(value)


async def start_sign_in(
    client: httpx.AsyncClient, *, action: str | None = None, suite: str | None = None
) -> httpx.Response:
    """`GET /api/auth/login`, as the interface sends the browser there."""
    params = {
        key: value for key, value in (("action", action), ("suite", suite)) if value is not None
    }
    return await client.get("/api/auth/login", params=params)


async def sign_in(
    client: httpx.AsyncClient,
    fake: FakeKeycloak,
    user: str,
    *,
    suite: str = "/",
    action: str | None = None,
    **changes: Any,
) -> httpx.Response:
    """A whole sign-in through the fake Keycloak, as `user` (an id of `fake.users`): the way
    there, Keycloak's pages (`fake.authorize`, whose identity token `changes` alter), and the
    answer of the way back."""
    started = await start_sign_in(client, action=action, suite=suite)
    assert started.status_code == 303, started.text
    location = started.headers["location"]
    code = fake.authorize(location, user, **changes)
    state = parse_qs(urlsplit(location).query)["state"][0]
    return await client.get("/api/auth/callback", params={"code": code, "state": state})
