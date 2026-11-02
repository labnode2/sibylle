"""The browsers connected to this API process, and the topics each one follows."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sibylle.realtime.bus import Message

log = logging.getLogger(__name__)

Send = Callable[[dict[str, Any]], Awaitable[None]]
Close = Callable[[int], Awaitable[None]]


async def _no_close(_code: int) -> None:
    return None


_NEWSROOM_ROLES = {"journalist", "editor"}


@dataclass(eq=False)
class Connection:
    account_id: uuid.UUID
    send: Send
    close: Close = _no_close
    # topic -> newsroom it belongs to (None for the private "me" topic)
    topics: dict[str, uuid.UUID | None] = field(default_factory=dict)
    # newsroom -> (membership id, role) of this account
    memberships: dict[uuid.UUID, tuple[uuid.UUID, str]] = field(default_factory=dict)

    @property
    def me_topic(self) -> str:
        return f"me:{self.account_id}"


class Hub:
    def __init__(self) -> None:
        self._connections: set[Connection] = set()

    def __len__(self) -> int:
        return len(self._connections)

    def add(self, connection: Connection) -> None:
        self._connections.add(connection)
        connection.topics[connection.me_topic] = None

    def remove(self, connection: Connection) -> None:
        self._connections.discard(connection)

    def subscribe(
        self,
        connection: Connection,
        topic: str,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
        role: str,
    ) -> None:
        connection.topics[topic] = org_id
        connection.memberships[org_id] = (membership_id, role)

    def unsubscribe(self, connection: Connection, topic: str) -> None:
        if topic != connection.me_topic:
            connection.topics.pop(topic, None)

    def _revoke(self, account_id: str, org_id: str) -> None:
        for connection in self._connections:
            if str(connection.account_id) != account_id:
                continue
            org = uuid.UUID(org_id)
            connection.memberships.pop(org, None)
            for topic, topic_org in list(connection.topics.items()):
                if topic_org == org:
                    del connection.topics[topic]

    def _allowed(self, connection: Connection, org_id: uuid.UUID | None, audience: Any) -> bool:
        if org_id is None or audience == "all":
            return True
        membership = connection.memberships.get(org_id)
        if membership is None:
            return False
        membership_id, role = membership
        if audience == "journalists":
            return role in _NEWSROOM_ROLES
        return isinstance(audience, list) and str(membership_id) in audience

    async def dispatch(self, message: Message) -> None:
        revoke = message.get("revoke")
        if revoke:
            self._revoke(revoke["account_id"], revoke["org_id"])
        for connection in list(self._connections):
            for topic in message.get("topics", []):
                if topic not in connection.topics:
                    continue
                org_id = connection.topics[topic]
                if not self._allowed(connection, org_id, message.get("audience", "all")):
                    continue
                envelope = {
                    "type": "event",
                    "topic": "me" if topic == connection.me_topic else topic,
                    "event": message["event"],
                    "at": message.get("at"),
                    "data": message.get("data", {}),
                }
                try:
                    await connection.send(envelope)
                except Exception:
                    log.info("dropping a closed real-time connection")
                    self.remove(connection)
                    break

    async def close_all(self, code: int) -> None:
        """Closes every connection, for instance with 1012 when the server restarts."""
        for connection in list(self._connections):
            try:
                await connection.close(code)
            except Exception:
                log.debug("connection already closed")
            self.remove(connection)
