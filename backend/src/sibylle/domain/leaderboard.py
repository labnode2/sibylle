"""The rankings: gold laurels, all time, or pronos won, over the month, the season or all time.

The laurels are the gold ones, engraved on the trophies of the closed seasons: they only exist
once a season is closed, so they are ranked all time only. The green laurels of the wallet are
not a ranking. The month and the season of the pronos won are taken in Paris time. Members who
left the newsroom, or whose account was deleted, are not ranked.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sibylle.domain.seasons import month_bounds, season_bounds, season_of


class Metric(StrEnum):
    LAURELS = "laurels"
    WINS = "wins"


class Period(StrEnum):
    MONTH = "month"
    SEASON = "season"
    ALL_TIME = "all_time"


def periods_of(metric: Metric) -> tuple[Period, ...]:
    """The gold laurels are engraved when a season closes: only all time makes sense for them."""
    if metric is Metric.LAURELS:
        return (Period.ALL_TIME,)
    return (Period.MONTH, Period.SEASON, Period.ALL_TIME)


@dataclass(frozen=True)
class Window:
    """From `start` (included) to `end` (excluded); `None` leaves that side open."""

    start: datetime | None
    end: datetime | None

    def contains(self, instant: datetime) -> bool:
        return (self.start is None or instant >= self.start) and (
            self.end is None or instant < self.end
        )


def window(period: Period, now: datetime) -> Window:
    if period is Period.MONTH:
        return Window(*month_bounds(now))
    if period is Period.SEASON:
        key = season_of(now)
        return Window(*season_bounds(key.year, key.name))
    return Window(None, None)


def is_ranked(status: str) -> bool:
    return status == "active"


@dataclass(frozen=True)
class Standing[K]:
    rank: int
    key: K
    value: int


def rank[K](values: Sequence[tuple[K, int]]) -> list[Standing[K]]:
    """Highest value first. Ties share a rank and the next rank is skipped (1, 1, 3); within a
    tie the given order is kept."""
    ordered = sorted(values, key=lambda item: -item[1])
    standings: list[Standing[K]] = []
    for position, (key, value) in enumerate(ordered, start=1):
        tied = standings and standings[-1].value == value
        standings.append(Standing(standings[-1].rank if tied else position, key, value))
    return standings


def on_podium(rank: int) -> bool:
    return rank <= 3
