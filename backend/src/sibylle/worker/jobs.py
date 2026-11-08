"""The worker's jobs. Each one reads the state in the database and moves it forward, so running
it twice, or after a restart, never does anything twice.

`sibylle jobs run <name>` runs one job once (tests, simulated clock); `sibylle worker` schedules
them all.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select

from sibylle import clock
from sibylle.config import get_settings
from sibylle.db.session import transaction
from sibylle.notify.dispatch import dispatch
from sibylle.notify.email import Renderer, SmtpSender
from sibylle.notify.push import WebPushSender

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


@job("dispatch_notifications", minute="*")
async def dispatch_notifications() -> int:
    settings = get_settings()
    push = WebPushSender(settings) if settings.vapid_private_key else None
    return await dispatch(SmtpSender(settings), Renderer(), push)


@job("closing_soon_alerts", minute="*")
async def closing_soon_alerts() -> int:
    """Queues « ferme dans 2 h » for the members who have not bet yet."""
    from sibylle.services import notifications

    async with transaction() as session:
        return await notifications.queue_closing_soon(session)


@job("designation_reminders", minute="*")
async def designation_reminders() -> int:
    """Queues the reminders of the results still to designate."""
    from sibylle.services import notifications

    async with transaction() as session:
        return await notifications.queue_designation_reminders(session)


@job("close_finished_seasons", minute="*")
async def close_finished_seasons(org_id: uuid.UUID | None = None) -> int:
    """Closes each newsroom's season once it is over and its bets have their results; returns
    how many closures were done.

    Checked every minute rather than once at midnight, so that a worker restarted after
    midnight, or a last result designated days later, still closes the season straight away.
    Seasons held back close one after the other, oldest first. `org_id` keeps one newsroom only
    (`sibylle seasons close --org`, for tests on a shared database).
    """
    from sibylle.services import seasons

    async with transaction() as session:
        await seasons.ensure_seasons(session)
    closed = 0
    while True:
        async with transaction() as session:
            due = await seasons.due(session, org_id)
        done = 0
        for org, season_id in due:
            async with transaction() as session:
                done += await seasons.close(session, org, season_id)
        closed += done
        if not done:
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


@job("pay_runner_week", minute="*")
async def pay_runner_week(org_id: uuid.UUID | None = None) -> int:
    """Pays the ball's race of the past week, once per newsroom, from Monday 00:30 (Paris): a
    run started on Sunday evening may still finish until then. A week whose games no longer had
    the race when it ended pays nothing (research.md J7).

    Checked every minute, like the coins, so that a worker restarted later still pays. `org_id`
    keeps one newsroom only (`sibylle games pay-runner --org`, for tests on a shared database).
    """
    from sibylle.services import minigames

    async with transaction() as session:
        return await minigames.pay_runner_week(session, org_id=org_id)


@job("reveal_pixel_puzzles", minute="*")
async def reveal_pixel_puzzles(org_id: uuid.UUID | None = None) -> int:
    """Shows each morning's Pixel mystère pixels at 08:00 (Paris), ends the drawings fully shown,
    and starts the next ones. A week without Pixel mystère ends the drawing in play at its first
    minute, its word given, and starts none (research.md J7). Checked every minute, so that a
    worker restarted later catches up. `org_id` keeps one newsroom only (`sibylle games
    reveal-pixel --org`)."""
    from sibylle.services import minigames

    async with transaction() as session:
        return await minigames.reveal_pixel_puzzles(session, org_id=org_id)


@job("purge_sign_in_attempts", hour=4, minute=10)
async def purge_sign_in_attempts() -> int:
    """Deletes, once a day, the sign-ins through Keycloak started and never finished, past their
    10 minutes (specs/002-keycloak-auth/data-model.md); returns how many went."""
    from sibylle.db.models import SignInAttempt

    async with transaction() as session:
        expired = await session.scalars(
            delete(SignInAttempt)
            .where(SignInAttempt.expires_at <= clock.now())
            .returning(SignInAttempt.id)
        )
        return len(expired.all())


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
