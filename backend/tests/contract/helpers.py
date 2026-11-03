"""Small helpers shared by the contract tests."""

import re
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select, update

from sibylle.db.models import CoinEntry, Membership, Notification
from sibylle.db.session import transaction
from sibylle.domain.content import AVATAR_TEMPLATES

AVATAR: dict[str, Any] = AVATAR_TEMPLATES[0]["image"]
PRIVATE_KEYS = {"email", "first_name", "last_name", "password_hash"}


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
