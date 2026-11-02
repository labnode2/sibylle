"""Real-time events, carried by PostgreSQL's NOTIFY.

An event is published inside the transaction that caused it: PostgreSQL delivers it only when
that transaction commits, and drops it if it rolls back. The API process listens on the channel
and hands each event to the hub, which forwards it to the browsers allowed to see it. The worker
publishes the same way, so no message broker is needed.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sybille import clock

CHANNEL = "sybille_events"
# PostgreSQL refuses payloads of 8000 bytes or more; bigger events become a "reload" hint.
MAX_PAYLOAD = 7500

log = logging.getLogger(__name__)

Message = dict[str, Any]


def encode(
    event: str,
    data: dict[str, Any],
    *,
    topics: Sequence[str],
    audience: str | Sequence[uuid.UUID] = "all",
    revoke: dict[str, str] | None = None,
) -> str:
    message: Message = {
        "event": event,
        "topics": list(topics),
        "audience": audience if isinstance(audience, str) else [str(a) for a in audience],
        "at": clock.now().isoformat(),
        "data": data,
    }
    if revoke:
        message["revoke"] = revoke
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(payload.encode()) > MAX_PAYLOAD:
        message["data"] = {"reload": True}
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"), default=str)
    return payload


async def publish(
    session: AsyncSession,
    event: str,
    data: dict[str, Any],
    *,
    topics: Sequence[str],
    audience: str | Sequence[uuid.UUID] = "all",
    revoke: dict[str, str] | None = None,
) -> None:
    """Queues an event; it leaves when the session's transaction commits.

    `audience` is "all", "journalists" (journalists and editors of the topic's newsroom) or a list
    of membership ids. `revoke` ({"account_id", "org_id"}) drops a member's subscriptions to that
    newsroom, for a member who leaves or is removed.
    """
    payload = encode(event, data, topics=topics, audience=audience, revoke=revoke)
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": payload}
    )


def asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


class Listener:
    """Listens on the channel with its own connection, reconnecting if it drops."""

    def __init__(
        self, dsn: str, on_message: Callable[[Message], Coroutine[Any, Any, None]]
    ) -> None:
        self.dsn = dsn
        self.on_message = on_message
        self.ready = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._pending: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.ready.clear()

    def _receive(self, _conn: object, _pid: int, _channel: str, payload: object) -> None:
        try:
            message = json.loads(str(payload))
        except ValueError:
            log.warning("unreadable real-time event", extra={"payload": str(payload)[:200]})
            return
        task = asyncio.create_task(self.on_message(message))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _run(self) -> None:
        delay = 1.0
        while True:
            conn: asyncpg.Connection | None = None
            try:
                conn = await asyncpg.connect(self.dsn)
                lost = asyncio.Event()
                conn.add_termination_listener(lambda _c, lost=lost: lost.set())
                await conn.add_listener(CHANNEL, self._receive)
                self.ready.set()
                delay = 1.0
                while not lost.is_set():
                    try:
                        await asyncio.wait_for(lost.wait(), timeout=30)
                    except TimeoutError:
                        await conn.fetchval("SELECT 1")  # notices a silently dropped connection
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("real-time listener lost its connection")
            finally:
                self.ready.clear()
                if conn is not None and not conn.is_closed():
                    await conn.close()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)
