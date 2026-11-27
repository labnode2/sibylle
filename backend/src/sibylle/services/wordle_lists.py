"""Wordle's word file (domain/wordle_words.py): fetched each night by the worker, kept in
`wordle_lists` once it passed its checks, read by the game.

The worker's `prepare_wordle_day` syncs the file once a day (Paris), from midnight on: it
downloads Settings.wordle_lists_url and checks it before anything uses it. A file that changed
makes a new row; the same file again only marks the latest row checked. A download or a check
that fails is logged as a warning and tried again at most every quarter of an hour until one
works, the latest good version staying in use; a new day tries again at once, before its words
are drawn. The worker keeps that failure in memory: once restarted, it tries again at once.

The game always uses the latest version. Each process keeps it in memory and looks at the latest
row's id at most once a minute, to load a new one. Until a first version is fetched, the game uses
the lists written by hand, whose words have no level.

The tests never reach the network: they put a fake in place of the download (`use_download`).
"""

import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sibylle import clock
from sibylle.config import get_settings
from sibylle.db.models import WordleList
from sibylle.db.session import transaction
from sibylle.domain.seasons import PARIS
from sibylle.domain.wordle_words import OLD_LISTS, InvalidLists, WordLists, decode, lists_from

log = logging.getLogger(__name__)

# Seconds for the whole download, and the most the file may weigh (150 kB in November 2026).
TIMEOUT = 30.0
MAX_BYTES = 5_000_000
# After a failed sync, the next one waits this long.
RETRY_AFTER = timedelta(minutes=15)
# Seconds between two looks at the latest version's id.
LOOK_EVERY = 60.0

Download = Callable[[str], Awaitable[bytes]]
Synced = Literal["stored", "unchanged", "failed", "not_due"]


class DownloadFailed(Exception):
    """The file did not come."""


async def _download(url: str) -> bytes:
    """The file at `url`. DownloadFailed when it does not come within TIMEOUT seconds, when the
    server answers with an error, or past MAX_BYTES."""
    try:
        async with asyncio.timeout(TIMEOUT):
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise DownloadFailed(f"more than {MAX_BYTES} bytes")
                    return bytes(body)
    except (httpx.HTTPError, TimeoutError) as error:
        raise DownloadFailed(repr(error)) from error


@dataclass
class _Kept:
    """What a process keeps between calls."""

    download: Download = _download
    # The last sync that failed, on the game's clock.
    failed_at: datetime | None = None
    # The latest version's id when it was last looked at (time.monotonic()), and the words in
    # use then: those of the latest version that holds, else the lists written by hand.
    version: int | None = None
    lists: WordLists = OLD_LISTS
    looked_at: float = float("-inf")


_kept = _Kept()


def use_download(download: Download | None) -> None:
    """Downloads the file with `download` (the tests' fake), or over the network with None, and
    forgets what this process kept."""
    _kept.download = download or _download
    forget()


def forget() -> None:
    """Forgets the words in memory and the last failure: the next use reads the database."""
    _kept.failed_at = None
    _forget_words()


def _forget_words() -> None:
    _kept.version, _kept.lists, _kept.looked_at = None, OLD_LISTS, float("-inf")


def _day(instant: datetime) -> date:
    return instant.astimezone(PARIS).date()


async def _due(session: AsyncSession, now: datetime) -> bool:
    """Today's sync is still to do: no version was found good today (Paris), and no sync failed
    today in the last quarter of an hour."""
    failed = _kept.failed_at
    if failed is not None and _day(failed) == _day(now) and failed <= now < failed + RETRY_AFTER:
        return False
    checked = await session.scalar(
        select(WordleList.checked_at).order_by(WordleList.id.desc()).limit(1)
    )
    return checked is None or _day(checked) != _day(now)


async def sync() -> Synced:
    """Today's sync of the word file, if it is still to do: downloaded and checked, then kept as
    a new version if it changed, or the latest version marked checked. Returns what it did. It
    opens its own transactions, none of them held during the download."""
    async with transaction() as session:
        if not await _due(session, clock.now()):
            return "not_due"
    url = get_settings().wordle_lists_url
    try:
        raw = await _kept.download(url)
        content = decode(raw)
        lists = lists_from(content)
    # Whatever went wrong, the latest version stays in use.
    except Exception as error:
        _kept.failed_at = clock.now()
        log.warning("wordle lists not synced", extra={"url": url, "error": repr(error)})
        return "failed"
    _kept.failed_at = None
    digest = hashlib.sha256(raw).hexdigest()
    now = clock.now()
    async with transaction() as session:
        latest = await session.scalar(
            select(WordleList).order_by(WordleList.id.desc()).limit(1).with_for_update()
        )
        if latest is not None and latest.sha256 == digest:
            latest.checked_at = now
            return "unchanged"
        session.add(WordleList(sha256=digest, content=content, fetched_at=now, checked_at=now))
    log.info(
        "wordle lists stored",
        extra={
            "sha256": digest,
            "answers": sum(len(tier) for tier in lists.tiers),
            "guesses": len(lists.guesses),
        },
    )
    # This process takes the new version at once.
    _forget_words()
    return "stored"


async def current(session: AsyncSession) -> WordLists:
    """The words the game uses: those of the latest version, else the lists written by hand.
    Looks at the latest version's id at most once a minute."""
    now = time.monotonic()
    if now - _kept.looked_at >= LOOK_EVERY:
        latest = await session.scalar(select(func.max(WordleList.id)))
        if latest != _kept.version:
            _kept.version, _kept.lists = latest, await _load(session, latest)
        _kept.looked_at = now
    return _kept.lists


async def _load(session: AsyncSession, latest: int | None) -> WordLists:
    """The words of the latest version up to `latest` that passes the checks, which may have
    grown since it was kept; the lists written by hand when none does."""
    if latest is None:
        return OLD_LISTS
    versions = await session.scalars(
        select(WordleList.id).where(WordleList.id <= latest).order_by(WordleList.id.desc())
    )
    for version in versions.all():
        content = await session.scalar(select(WordleList.content).where(WordleList.id == version))
        try:
            return lists_from(content)
        except InvalidLists as error:
            log.warning(
                "wordle lists version unusable", extra={"version": version, "error": repr(error)}
            )
    return OLD_LISTS
