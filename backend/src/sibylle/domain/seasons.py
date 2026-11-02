"""Seasons, weeks and months, all computed in Paris time.

The seasons are the crystal ball's: spring from 21 March to 20 June, summer from 21 June to
22 September, autumn from 23 September to 20 December, winter from 21 December to 20 March.
Each one starts at 00:00 in Paris, and winter carries the year it starts in.

Bounds come back as UTC instants: Python subtracts two datetimes that share a tzinfo as wall-clock
times, which would hide the hour gained or lost when Paris changes time.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, get_args
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

SeasonName = Literal["spring", "summer", "autumn", "winter"]
SEASON_NAMES: tuple[SeasonName, ...] = get_args(SeasonName)

# First day of each season, in the order they come within a calendar year.
_STARTS: dict[SeasonName, tuple[int, int]] = {
    "spring": (3, 21),
    "summer": (6, 21),
    "autumn": (9, 23),
    "winter": (12, 21),
}
_NEXT: dict[SeasonName, SeasonName] = {
    "spring": "summer",
    "summer": "autumn",
    "autumn": "winter",
    "winter": "spring",
}


@dataclass(frozen=True)
class SeasonKey:
    year: int
    name: SeasonName


def _midnight(day: date) -> datetime:
    """00:00 in Paris on that day, as a UTC instant."""
    return datetime(day.year, day.month, day.day, tzinfo=PARIS).astimezone(UTC)


def next_season(key: SeasonKey) -> SeasonKey:
    following = _NEXT[key.name]
    return SeasonKey(key.year + 1 if key.name == "winter" else key.year, following)


def season_bounds(year: int, name: SeasonName) -> tuple[datetime, datetime]:
    """Start (included) and end (excluded) of a season."""
    month, day = _STARTS[name]
    following = next_season(SeasonKey(year, name))
    next_month, next_day = _STARTS[following.name]
    return (
        _midnight(date(year, month, day)),
        _midnight(date(following.year, next_month, next_day)),
    )


def season_of(instant: datetime) -> SeasonKey:
    local = instant.astimezone(PARIS)
    month_day = (local.month, local.day)
    if month_day >= _STARTS["winter"]:
        return SeasonKey(local.year, "winter")
    if month_day >= _STARTS["autumn"]:
        return SeasonKey(local.year, "autumn")
    if month_day >= _STARTS["summer"]:
        return SeasonKey(local.year, "summer")
    if month_day >= _STARTS["spring"]:
        return SeasonKey(local.year, "spring")
    return SeasonKey(local.year - 1, "winter")


def seasons_between(first: SeasonKey, last: SeasonKey) -> list[SeasonKey]:
    """Every season from `first` to `last`, both included."""
    keys = []
    key = first
    while _order(key) <= _order(last):
        keys.append(key)
        key = next_season(key)
    return keys


def _order(key: SeasonKey) -> tuple[int, int]:
    return key.year, list(_STARTS).index(key.name)


def week_start(instant: datetime) -> date:
    """The Monday of the instant's week, in Paris."""
    local = instant.astimezone(PARIS).date()
    return local - timedelta(days=local.weekday())


def week_bounds(instant: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 (included) to the next Monday 00:00 (excluded), in Paris."""
    monday = week_start(instant)
    return _midnight(monday), _midnight(monday + timedelta(days=7))


def month_bounds(instant: datetime) -> tuple[datetime, datetime]:
    """First day of the month 00:00 (included) to the first day of the next month, in Paris."""
    local = instant.astimezone(PARIS)
    first = date(local.year, local.month, 1)
    if local.month == 12:
        following = date(local.year + 1, 1, 1)
    else:
        following = date(local.year, local.month + 1, 1)
    return _midnight(first), _midnight(following)
