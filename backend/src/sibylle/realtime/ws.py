"""The WebSocket endpoint (contracts/realtime.md): one connection per tab, topics per screen."""

import asyncio
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from sibylle.api.deps import SESSION_COOKIE, account_from_token, member_of
from sibylle.config import get_settings
from sibylle.db.models import Prono
from sibylle.db.session import transaction
from sibylle.realtime.hub import Connection, Hub
from sibylle.services.pronos import visible_to

PING_EVERY = 25.0
PONG_TIMEOUT = 60.0
CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403

log = logging.getLogger(__name__)
router = APIRouter()


async def _authenticate(token: str | None) -> uuid.UUID | None:
    async with transaction() as session:
        account = await account_from_token(session, token)
        return account.id if account else None


async def authorize(account_id: uuid.UUID, topic: str) -> tuple[uuid.UUID, uuid.UUID, str] | None:
    """(newsroom, membership, role) when the account may follow the topic, else None."""
    kind, _, raw_id = topic.partition(":")
    try:
        target = uuid.UUID(raw_id)
    except ValueError:
        return None
    async with transaction() as session:
        if kind == "org":
            org_id = target
        elif kind == "prono":
            prono = await session.get(Prono, target)
            if prono is None:
                return None
            org_id = prono.org_id
        else:
            return None
        member = await member_of(session, org_id, account_id)
        if member is None:
            return None
        if kind == "prono":
            visible = await session.scalar(
                select(Prono.id).where(Prono.id == target, visible_to(member))
            )
            if visible is None:
                return None
        return (member.org_id, member.id, member.role)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    hub: Hub | None = getattr(websocket.app.state, "hub", None)
    if websocket.headers.get("origin") != get_settings().public_origin or hub is None:
        await websocket.close(code=CLOSE_FORBIDDEN)
        return
    account_id = await _authenticate(websocket.cookies.get(SESSION_COOKIE))
    await websocket.accept()
    if account_id is None:
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    async def close(code: int) -> None:
        await websocket.close(code=code)

    connection = Connection(account_id=account_id, send=websocket.send_json, close=close)
    hub.add(connection)
    last_pong = time.monotonic()

    async def keep_alive() -> None:
        while True:
            await asyncio.sleep(PING_EVERY)
            if time.monotonic() - last_pong > PONG_TIMEOUT:
                await websocket.close()
                return
            await websocket.send_json({"type": "ping"})

    pinger = asyncio.create_task(keep_alive())
    try:
        while True:
            message: dict[str, Any] = await websocket.receive_json()
            kind = message.get("type")
            topics = [t for t in message.get("topics", []) if isinstance(t, str)]
            if kind == "pong":
                last_pong = time.monotonic()
            elif kind == "subscribe":
                accepted = []
                for topic in topics:
                    if topic == "me":
                        accepted.append(topic)
                        continue
                    grant = await authorize(account_id, topic)
                    if grant is None:
                        await websocket.send_json(
                            {"type": "error", "code": "forbidden_topic", "topic": topic}
                        )
                        continue
                    hub.subscribe(connection, topic, *grant)
                    accepted.append(topic)
                await websocket.send_json({"type": "subscribed", "topics": accepted})
            elif kind == "unsubscribe":
                for topic in topics:
                    hub.unsubscribe(connection, topic)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("real-time connection failed")
    finally:
        pinger.cancel()
        hub.remove(connection)
