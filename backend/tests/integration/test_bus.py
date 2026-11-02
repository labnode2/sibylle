import asyncio
import json

import pytest

from sibylle.db.session import transaction
from sibylle.realtime import bus
from sibylle.realtime.bus import Listener, Message, asyncpg_dsn

pytestmark = pytest.mark.integration


async def _listen(database_url: str) -> tuple[Listener, asyncio.Queue[Message]]:
    received: asyncio.Queue[Message] = asyncio.Queue()

    async def on_message(message: Message) -> None:
        await received.put(message)

    listener = Listener(asyncpg_dsn(database_url), on_message)
    await listener.start()
    await asyncio.wait_for(listener.ready.wait(), timeout=10)
    return listener, received


async def test_an_event_leaves_when_the_transaction_commits(db: None, database_url: str) -> None:
    listener, received = await _listen(database_url)
    try:
        async with transaction() as session:
            await bus.publish(session, "bet.placed", {"pot": 40}, topics=["prono:abc"])
            await asyncio.sleep(0.2)
            assert received.empty()  # nothing before the commit
        message = await asyncio.wait_for(received.get(), timeout=5)
        assert message["event"] == "bet.placed"
        assert message["topics"] == ["prono:abc"]
        assert message["audience"] == "all"
        assert message["data"] == {"pot": 40}
    finally:
        await listener.stop()


async def test_a_rolled_back_event_never_leaves(db: None, database_url: str) -> None:
    listener, received = await _listen(database_url)
    try:
        with pytest.raises(RuntimeError):
            async with transaction() as session:
                await bus.publish(session, "bet.placed", {}, topics=["prono:abc"])
                raise RuntimeError("rollback")
        async with transaction() as session:
            await bus.publish(session, "marker", {}, topics=["org:x"])
        message = await asyncio.wait_for(received.get(), timeout=5)
        assert message["event"] == "marker"
    finally:
        await listener.stop()


def test_an_oversized_event_becomes_a_reload_hint() -> None:
    payload = bus.encode("prono.edited", {"blob": "x" * 9000}, topics=["org:x"])
    assert len(payload.encode()) < bus.MAX_PAYLOAD
    assert json.loads(payload)["data"] == {"reload": True}
