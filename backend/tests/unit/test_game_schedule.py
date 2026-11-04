"""The games of a week (research.md J7): its own planning, or else those of an ordinary week as
set from the latest Monday not after it; the editor plans this week and the three after it."""

from datetime import date, datetime

import pytest

from sibylle.domain.game_schedule import (
    GAMES,
    horizon,
    normalized,
    ordinary_games,
    week_games,
    week_problem,
)
from sibylle.domain.seasons import PARIS

pytestmark = pytest.mark.unit


def test_games_come_in_their_order_and_once() -> None:
    assert GAMES == ("runner", "pixel")
    assert normalized(["pixel", "runner", "pixel"]) == ("runner", "pixel")
    assert normalized(["pixel"]) == ("pixel",)
    assert normalized([]) == ()


def test_an_ordinary_week_has_both_games_until_the_editor_changes_it() -> None:
    assert ordinary_games([], date(2026, 11, 2)) == ("runner", "pixel")


def test_a_change_holds_from_its_monday_on() -> None:
    defaults = [(date(2026, 11, 23), []), (date(2026, 11, 9), ["pixel"])]
    assert ordinary_games(defaults, date(2026, 11, 2)) == ("runner", "pixel")
    assert ordinary_games(defaults, date(2026, 11, 9)) == ("pixel",)
    assert ordinary_games(defaults, date(2026, 11, 16)) == ("pixel",)
    assert ordinary_games(defaults, date(2026, 11, 23)) == ()
    assert ordinary_games(defaults, date(2027, 1, 4)) == ()


def test_a_planned_week_keeps_its_own_games() -> None:
    planned = {date(2026, 11, 16): ["runner"], date(2026, 11, 23): []}
    defaults = [(date(2026, 11, 9), ["pixel"])]
    assert week_games(date(2026, 11, 2), planned, defaults) == ("runner", "pixel")
    assert week_games(date(2026, 11, 9), planned, defaults) == ("pixel",)
    assert week_games(date(2026, 11, 16), planned, defaults) == ("runner",)
    # A week may have no game at all.
    assert week_games(date(2026, 11, 23), planned, defaults) == ()


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 11, 2, 0, 0, tzinfo=PARIS),
        datetime(2026, 11, 4, 10, 0, tzinfo=PARIS),
        datetime(2026, 11, 8, 23, 59, tzinfo=PARIS),
    ],
)
def test_the_editor_plans_this_week_and_the_three_after_it(now: datetime) -> None:
    assert horizon(now) == [
        date(2026, 11, 2),
        date(2026, 11, 9),
        date(2026, 11, 16),
        date(2026, 11, 23),
    ]


def test_only_a_monday_within_the_four_weeks_can_be_planned() -> None:
    now = datetime(2026, 11, 4, 10, 0, tzinfo=PARIS)
    assert week_problem(date(2026, 11, 2), now) is None
    assert week_problem(date(2026, 11, 23), now) is None
    assert week_problem(date(2026, 11, 3), now) == "not_monday"
    assert week_problem(date(2026, 10, 26), now) == "out_of_range"
    assert week_problem(date(2026, 11, 30), now) == "out_of_range"
