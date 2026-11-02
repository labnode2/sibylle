"""The worker's jobs. Each one reads the state in the database and moves it forward, so running
it twice, or after a restart, never does anything twice.

`sybille jobs run <name>` runs one job once (tests, simulated clock); `sybille worker` schedules
them all.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from sybille import clock
from sybille.config import get_settings
from sybille.db.models import Account, Notification
from sybille.db.session import transaction
from sybille.notify.email import Renderer, Sender, SmtpSender

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    name: str
    # APScheduler cron fields in Paris time, for instance {"minute": "*"}.
    cron: dict[str, Any]
    run: Callable[[], Awaitable[Any]]


REGISTRY: dict[str, Job] = {}


def job(
    name: str, **cron: Any
) -> Callable[[Callable[[], Awaitable[Any]]], Callable[[], Awaitable[Any]]]:
    def register(run: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[Any]]:
        REGISTRY[name] = Job(name, cron, run)
        return run

    return register


# Retries after a failed send, then the notification is given up as "failed".
RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
)


async def _recipient(notification: Notification, session: Any) -> str | None:
    if notification.account_id is None:
        to = notification.payload.get("to")
        return str(to) if to else None
    account = await session.get(Account, notification.account_id)
    if account is None or account.deleted_at is not None or not account.email:
        return None
    return str(account.email)


async def dispatch(sender: Sender, renderer: Renderer, *, batch: int = 50) -> int:
    """Sends the notifications that are due; returns how many were handled."""
    async with transaction() as session:
        due = (
            await session.scalars(
                select(Notification)
                .where(Notification.state == "pending", Notification.next_attempt_at <= clock.now())
                .order_by(Notification.next_attempt_at)
                .limit(batch)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for notification in due:
            to = await _recipient(notification, session)
            if to is None:
                notification.state = "skipped"
                continue
            try:
                mail = renderer.render(notification.type, to, notification.payload)
                await sender.send(mail)
            except Exception:
                log.warning(
                    "notification not sent",
                    extra={"notification_id": str(notification.id), "type": notification.type},
                    exc_info=True,
                )
                notification.attempts += 1
                if notification.attempts > len(RETRY_DELAYS):
                    notification.state = "failed"
                else:
                    delay = RETRY_DELAYS[notification.attempts - 1]
                    notification.next_attempt_at = clock.now() + delay
                continue
            notification.state = "sent"
            notification.sent_at = clock.now()
        return len(due)


@job("dispatch_notifications", minute="*")
async def dispatch_notifications() -> int:
    return await dispatch(SmtpSender(get_settings()), Renderer())


@job("advance_pronos", minute="*")
async def advance_pronos() -> int:
    """Opens the scheduled pronos and closes the open ones whose time has come."""
    from sybille.db.models import Prono
    from sybille.domain.lifecycle import State
    from sybille.services.pronos import set_state

    async with transaction() as session:
        now = clock.now()
        due = (
            await session.scalars(
                select(Prono)
                .where(
                    (
                        (Prono.state == State.SCHEDULED.value)
                        & Prono.opens_at.is_not(None)
                        & (Prono.opens_at <= now)
                    )
                    | (
                        (Prono.state == State.OPEN.value)
                        & Prono.closes_at.is_not(None)
                        & (Prono.closes_at <= now)
                    )
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        for prono in due:
            if prono.state == State.SCHEDULED.value:
                await set_state(session, prono, State.OPEN, "opened")
            else:
                await set_state(session, prono, State.CLOSED, "closed")
        return len(due)
