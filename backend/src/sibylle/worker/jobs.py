"""The worker's jobs. Each one reads the state in the database and moves it forward, so running
it twice, or after a restart, never does anything twice.

`sibylle jobs run <name>` runs one job once (tests, simulated clock); `sibylle worker` schedules
them all.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from sibylle import clock
from sibylle.config import get_settings
from sibylle.db.models import Account, Notification
from sibylle.db.session import transaction
from sibylle.notify.email import Renderer, Sender, SmtpSender

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    name: str
    # APScheduler cron fields in Paris time, for instance {"minute": "*"}.
    cron: dict[str, Any]
    run: Callable[[], Awaitable[Any]]


REGISTRY: dict[str, Job] = {}


def job[F: Callable[..., Awaitable[Any]]](name: str, **cron: Any) -> Callable[[F], F]:
    """Registers a job; it keeps its own signature for direct calls."""

    def register(run: F) -> F:
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


@job("close_finished_seasons", minute="*")
async def close_finished_seasons(org_id: uuid.UUID | None = None) -> int:
    """Closes each newsroom's season once it is over; returns how many closures were done.

    Checked every minute rather than once at midnight, so that a worker restarted after
    midnight still closes the season straight away. `org_id` keeps one newsroom only
    (`sibylle seasons close --org`, for tests on a shared database).
    """
    from sibylle.services import seasons

    async with transaction() as session:
        await seasons.ensure_seasons(session)
        due = await seasons.due(session, org_id)
    closed = 0
    for org_id, season_id in due:
        async with transaction() as session:
            closed += await seasons.close(session, org_id, season_id)
    return closed


@job("grant_weekly_coins", minute="*")
async def grant_weekly_coins(org_id: uuid.UUID | None = None) -> int:
    """Turns each member's gold laurels into coins, once a week from Monday 00:00 (Paris).

    Checked every minute, like the season closure, so that a worker restarted later on Monday
    still does the week's conversion. `org_id` keeps one newsroom only (`sibylle coins grant
    --org`, for tests on a shared database).
    """
    from sibylle.services import coins

    async with transaction() as session:
        return await coins.grant_week(session, org_id=org_id)


@job("advance_pronos", minute="*")
async def advance_pronos() -> int:
    """Opens the scheduled pronos and closes the open ones whose time has come."""
    from sibylle.db.models import Prono
    from sibylle.domain.lifecycle import State
    from sibylle.services.pronos import set_state

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
