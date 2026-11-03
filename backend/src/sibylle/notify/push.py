"""Web Push (VAPID): the message is encrypted for the device and handed to its browser's push
service, which keeps it 12 hours for a device that is off."""

import json
from dataclasses import dataclass, field
from typing import Protocol

from pywebpush import WebPushException, webpush_async

from sibylle.config import Settings
from sibylle.domain.notifications import PUSH_TTL


class Gone(Exception):
    """The push service no longer knows this subscription (404 or 410): it is removed."""


@dataclass(frozen=True)
class Device:
    endpoint: str
    p256dh: str
    auth: str


class PushSender(Protocol):
    async def send(self, device: Device, message: dict[str, str], *, urgency: str) -> None: ...


class WebPushSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, device: Device, message: dict[str, str], *, urgency: str) -> None:
        try:
            await webpush_async(
                subscription_info={
                    "endpoint": device.endpoint,
                    "keys": {"p256dh": device.p256dh, "auth": device.auth},
                },
                data=json.dumps(message, ensure_ascii=False),
                vapid_private_key=self.settings.vapid_private_key,
                # pywebpush adds `aud` and `exp` to the dict it gets: a fresh one each time.
                vapid_claims={"sub": self.settings.vapid_subject},
                ttl=int(PUSH_TTL.total_seconds()),
                headers={"Urgency": urgency},
                timeout=10,
            )
        except WebPushException as error:
            if error.status_code in (404, 410):
                raise Gone(device.endpoint) from error
            raise


@dataclass
class MemoryPushSender:
    """Keeps the messages instead of sending them (tests)."""

    sent: list[tuple[str, dict[str, str], str]] = field(default_factory=list)
    gone: set[str] = field(default_factory=set)
    fail: bool = False

    async def send(self, device: Device, message: dict[str, str], *, urgency: str) -> None:
        if device.endpoint in self.gone:
            raise Gone(device.endpoint)
        if self.fail:
            raise ConnectionError("push service unavailable")
        self.sent.append((device.endpoint, message, urgency))
