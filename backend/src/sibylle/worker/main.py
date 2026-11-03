"""The worker process: runs the registered jobs on their schedule, in Paris time."""

import asyncio
import logging
import signal
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sibylle.config import get_settings
from sibylle.db.session import dispose_engine
from sibylle.domain.seasons import PARIS
from sibylle.logs import configure_logging
from sibylle.worker.jobs import REGISTRY

log = logging.getLogger(__name__)

# The scheduler touches this file every 30 seconds; the container's health check
# (`sibylle worker --check`) reads its age.
HEARTBEAT = Path(tempfile.gettempdir()) / "sibylle-worker.alive"
HEARTBEAT_EVERY = timedelta(seconds=30)
HEARTBEAT_MAX_AGE = timedelta(minutes=2)


async def beat() -> None:
    HEARTBEAT.touch()


def alive() -> bool:
    """The scheduler beat less than two minutes ago."""
    try:
        age = time.time() - HEARTBEAT.stat().st_mtime
    except FileNotFoundError:
        return False
    return age < HEARTBEAT_MAX_AGE.total_seconds()


async def run_worker() -> None:
    configure_logging(get_settings().log_level)
    scheduler = AsyncIOScheduler(timezone=PARIS)
    for job in REGISTRY.values():
        scheduler.add_job(
            job.run,
            CronTrigger(timezone=PARIS, **job.cron),
            id=job.name,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
    scheduler.add_job(
        beat,
        IntervalTrigger(seconds=HEARTBEAT_EVERY.total_seconds()),
        id="heartbeat",
        next_run_time=datetime.now(PARIS),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    scheduler.start()
    log.info("worker started", extra={"jobs": sorted(REGISTRY)})
    await stop.wait()
    scheduler.shutdown(wait=False)
    await dispose_engine()
    log.info("worker stopped")
