from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from sibylle.domain.seasons import (
    SeasonKey,
    edition_number,
    month_bounds,
    next_season,
    season_bounds,
    season_of,
    seasons_between,
    week_bounds,
    week_start,
)

pytestmark = pytest.mark.unit

PARIS = ZoneInfo("Europe/Paris")


def paris(*args: int) -> datetime:
    return datetime(*args, tzinfo=PARIS)


@pytest.mark.parametrize(
    ("name", "start", "end"),
    [
        ("spring", paris(2027, 3, 21), paris(2027, 6, 21)),
        ("summer", paris(2027, 6, 21), paris(2027, 9, 23)),
        ("autumn", paris(2027, 9, 23), paris(2027, 12, 21)),
        ("winter", paris(2027, 12, 21), paris(2028, 3, 21)),
    ],
)
def test_season_bounds_start_at_midnight(name: str, start: datetime, end: datetime) -> None:
    bounds = season_bounds(2027, name)  # type: ignore[arg-type]
    assert bounds == (start, end)
    assert bounds[0].tzinfo is not None


def test_winter_carries_the_year_it_starts_in() -> None:
    assert season_of(paris(2027, 1, 15, 12)) == SeasonKey(2026, "winter")
    assert season_of(paris(2026, 12, 21)) == SeasonKey(2026, "winter")
    assert season_of(paris(2027, 3, 20, 23, 59)) == SeasonKey(2026, "winter")
    assert season_of(paris(2027, 3, 21)) == SeasonKey(2027, "spring")


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (paris(2027, 6, 20, 23, 59), SeasonKey(2027, "spring")),
        (paris(2027, 6, 21), SeasonKey(2027, "summer")),
        (paris(2027, 9, 22, 23, 59), SeasonKey(2027, "summer")),
        (paris(2027, 9, 23), SeasonKey(2027, "autumn")),
        (paris(2027, 12, 20, 23, 59), SeasonKey(2027, "autumn")),
    ],
)
def test_season_of_each_boundary(instant: datetime, expected: SeasonKey) -> None:
    assert season_of(instant) == expected


def test_boundaries_follow_paris_time_not_utc() -> None:
    # 21 June 2027 00:00 in Paris (summer time, UTC+2) is still 20 June in UTC.
    start, _ = season_bounds(2027, "summer")
    assert start.astimezone(UTC) == datetime(2027, 6, 20, 22, tzinfo=UTC)
    assert season_of(datetime(2027, 6, 20, 21, 59, tzinfo=UTC)) == SeasonKey(2027, "spring")
    assert season_of(datetime(2027, 6, 20, 22, 0, tzinfo=UTC)) == SeasonKey(2027, "summer")
    # 21 December in winter time (UTC+1).
    start, _ = season_bounds(2026, "winter")
    assert start.astimezone(UTC) == datetime(2026, 12, 20, 23, tzinfo=UTC)


def test_launch_falls_in_a_short_autumn_2026() -> None:
    assert season_of(paris(2026, 12, 1, 9)) == SeasonKey(2026, "autumn")
    _, end = season_bounds(2026, "autumn")
    assert end == paris(2026, 12, 21)


def test_week_starts_on_monday_midnight_in_paris() -> None:
    assert week_start(paris(2026, 12, 2, 15)) == date(2026, 11, 30)
    assert week_start(paris(2026, 11, 30, 0, 0)) == date(2026, 11, 30)
    assert week_start(paris(2026, 11, 29, 23, 59)) == date(2026, 11, 23)


def test_week_bounds_across_the_end_of_summer_time() -> None:
    # Summer time ends on Sunday 25 October 2026: that week lasts 7 days and 1 hour.
    start, end = week_bounds(paris(2026, 10, 21, 12))
    assert start == paris(2026, 10, 19)
    assert end == paris(2026, 10, 26)
    assert end - start == timedelta(days=7, hours=1)


def test_month_bounds_in_paris() -> None:
    start, end = month_bounds(datetime(2026, 11, 30, 23, 30, tzinfo=UTC))  # 1 December in Paris
    assert start == paris(2026, 12, 1)
    assert end == paris(2027, 1, 1)


def test_next_season_and_ranges() -> None:
    assert next_season(SeasonKey(2026, "autumn")) == SeasonKey(2026, "winter")
    assert next_season(SeasonKey(2026, "winter")) == SeasonKey(2027, "spring")
    assert seasons_between(SeasonKey(2026, "autumn"), SeasonKey(2027, "summer")) == [
        SeasonKey(2026, "autumn"),
        SeasonKey(2026, "winter"),
        SeasonKey(2027, "spring"),
        SeasonKey(2027, "summer"),
    ]


def test_the_edition_number_counts_the_days_in_paris() -> None:
    created = datetime(2026, 1, 1, 9, 0, tzinfo=PARIS)
    assert edition_number(created, created) == 1
    # The first of November is day 305 of 2026: « N° 305 · DIM. 1 NOV. 2026 ».
    assert edition_number(created, datetime(2026, 11, 1, 23, 59, tzinfo=PARIS)) == 305
    # Midnight in Paris turns the page, whatever the time in UTC.
    assert edition_number(created, datetime(2026, 1, 1, 23, 30, tzinfo=UTC)) == 2
