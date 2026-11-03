"""The ball's race (research.md J3 and R19)."""

import uuid
from datetime import date, datetime, timedelta

import pytest

from sibylle.domain.minigames import (
    MAX_POINTS_PER_SECOND,
    RUN_MAX,
    RUNNER_ATTEMPTS,
    RunResult,
    plausible,
    rank_runner,
    runner_gains,
    week_to_pay,
)
from sibylle.domain.seasons import PARIS, week_start

pytestmark = pytest.mark.unit

T0 = datetime(2026, 11, 4, 20, 0, tzinfo=PARIS)
CAMI, LEO, MANON, HUGO = (uuid.uuid4() for _ in range(4))


def run(member: uuid.UUID, score: int, minutes: int = 0) -> RunResult:
    return RunResult(member, score, T0 + timedelta(minutes=minutes))


def test_five_attempts_a_week_from_monday_to_sunday_in_paris() -> None:
    assert RUNNER_ATTEMPTS == 5
    assert week_start(datetime(2026, 11, 8, 23, 59, 59, tzinfo=PARIS)) == date(2026, 11, 2)
    assert week_start(datetime(2026, 11, 9, 0, 0, tzinfo=PARIS)) == date(2026, 11, 9)


def test_the_best_score_counts_and_the_older_run_wins_a_tie() -> None:
    ranked = rank_runner(
        [
            run(CAMI, 300, 0),
            run(CAMI, 800, 5),
            run(LEO, 800, 3),
            run(MANON, 120, 1),
            run(LEO, 200, 9),
        ]
    )
    assert [(r.member_id, r.score) for r in ranked] == [(LEO, 800), (CAMI, 800), (MANON, 120)]


def test_ten_seven_five_then_two_for_every_other_player() -> None:
    ranked = rank_runner([run(m, s) for m, s in ((CAMI, 9), (LEO, 8), (MANON, 7), (HUGO, 6))])
    assert runner_gains(ranked) == [(CAMI, 10), (LEO, 7), (MANON, 5), (HUGO, 2)]
    assert runner_gains(ranked[:2]) == [(CAMI, 10), (LEO, 7)]
    assert runner_gains([]) == []


def test_a_score_that_cannot_be_reached_in_its_time_is_refused() -> None:
    minute = 60_000
    assert plausible(MAX_POINTS_PER_SECOND * 60, minute)
    assert not plausible(MAX_POINTS_PER_SECOND * 60 + 100, minute)
    assert plausible(5, 0)
    assert not plausible(-1, minute)
    # Longer than 30 minutes: refused whatever the score.
    assert plausible(10, int(RUN_MAX.total_seconds() * 1000))
    assert not plausible(10, int(RUN_MAX.total_seconds() * 1000) + 1)


def test_the_past_week_is_paid_once_its_last_runs_are_over() -> None:
    monday = datetime(2026, 11, 9, 0, 0, tzinfo=PARIS)
    # Until 00:30, a run started on Sunday evening may still finish: the week before is the
    # last one that can be paid (already paid, normally).
    assert week_to_pay(monday + timedelta(minutes=29)) == date(2026, 10, 26)
    assert week_to_pay(monday + RUN_MAX) == date(2026, 11, 2)
    assert week_to_pay(monday + timedelta(days=3)) == date(2026, 11, 2)
