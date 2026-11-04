"""The games of each week (US12, research.md J7).

The editor plans the current week and the three after it. A week without a planning of its own
takes the games of an ordinary week, a setting dated by the Monday from which it holds: a change
waits for the next Monday, so that a week never changes its games once begun unless the editor
plans that week itself.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Literal, get_args

from sibylle.domain.seasons import week_start

Game = Literal["runner", "pixel"]
# Every game, in the order they are shown and stored.
GAMES: tuple[Game, ...] = get_args(Game)
# The current week and the three after it.
HORIZON_WEEKS = 4


def normalized(games: Iterable[str]) -> tuple[Game, ...]:
    """The games in their usual order, each once."""
    chosen = set(games)
    return tuple(game for game in GAMES if game in chosen)


def horizon(now: datetime) -> list[date]:
    """The Mondays of the weeks the editor may plan: this one and the three after it."""
    first = week_start(now)
    return [first + timedelta(weeks=i) for i in range(HORIZON_WEEKS)]


def week_problem(week: date, now: datetime) -> Literal["not_monday", "out_of_range"] | None:
    """Why a week cannot be planned, or None when it can."""
    if week.weekday() != 0:
        return "not_monday"
    if week not in horizon(now):
        return "out_of_range"
    return None


def ordinary_games(defaults: Iterable[tuple[date, Sequence[str]]], week: date) -> tuple[Game, ...]:
    """The games of an ordinary week, as set from the latest Monday not after `week`; both games
    until the editor first changes them."""
    in_force = [(from_week, games) for from_week, games in defaults if from_week <= week]
    if not in_force:
        return GAMES
    return normalized(max(in_force, key=lambda row: row[0])[1])


def week_games(
    week: date,
    planned: Mapping[date, Sequence[str]],
    defaults: Iterable[tuple[date, Sequence[str]]],
) -> tuple[Game, ...]:
    """A week's games: its own planning, or else those of an ordinary week at that time."""
    if week in planned:
        return normalized(planned[week])
    return ordinary_games(defaults, week)
