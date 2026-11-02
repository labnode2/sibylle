"""The app's clock: the system clock, or a simulated one for development and tests.

Every business instant comes from `now()`, never from PostgreSQL's `now()`, so that the simulated
clock moves the whole game (closings, reminders, seasons, mini-games) at once.

The simulated clock lives in a small JSON file shared by the API, the worker and the command line:
it holds the simulated instant and the real instant it was set at, so time keeps flowing from there.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from sibylle.config import get_settings


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _state(self) -> tuple[datetime, datetime] | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        return datetime.fromisoformat(data["simulated"]), datetime.fromisoformat(data["set_at"])

    def now(self) -> datetime:
        real = datetime.now(UTC)
        state = self._state()
        if state is None:
            return real
        simulated, set_at = state
        return simulated + (real - set_at)

    def set(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("l'instant simulé doit avoir un fuseau horaire")
        state = {
            "simulated": instant.astimezone(UTC).isoformat(),
            "set_at": datetime.now(UTC).isoformat(),
        }
        self.path.write_text(json.dumps(state), encoding="utf-8")

    def advance(self, delta: timedelta) -> None:
        self.set(self.now() + delta)


_override: Clock | None = None


def set_clock(clock: Clock | None) -> None:
    """Replaces the clock (tests); `None` goes back to the one chosen by the settings."""
    global _override
    _override = clock


def get_clock() -> Clock:
    if _override is not None:
        return _override
    settings = get_settings()
    if settings.sibylle_clock == "fake":
        return FakeClock(settings.sibylle_fake_clock_file)
    return SystemClock()


def now() -> datetime:
    return get_clock().now()


def fake_clock() -> FakeClock:
    clock = get_clock()
    if not isinstance(clock, FakeClock):
        raise RuntimeError("l'horloge simulée n'est pas active (SIBYLLE_CLOCK=fake)")
    return clock


def set_fake_now(instant: datetime) -> None:
    fake_clock().set(instant)


def advance_fake(delta: timedelta) -> None:
    fake_clock().advance(delta)
