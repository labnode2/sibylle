"""Small helpers shared by the contract tests."""

import re
from typing import Any

import httpx
from sqlalchemy import select

from sybille.db.models import Notification
from sybille.db.session import transaction
from sybille.domain.content import AVATAR_TEMPLATES

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
