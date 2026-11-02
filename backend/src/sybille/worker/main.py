"""The worker process: runs the registered jobs on their schedule, in Paris time."""

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sybille.config import get_settings
from sybille.db.session import dispose_engine
from sybille.domain.seasons import PARIS
from sybille.logs import configure_logging
from sybille.worker.jobs import REGISTRY

log = logging.getLogger(__name__)


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
