"""Rules of the mini-games: the ball's race (research.md J3 and R19)."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sibylle.domain.seasons import week_bounds, week_start

RUNNER_ATTEMPTS = 5
# A run open longer than this can no longer be finished.
RUN_MAX = timedelta(minutes=30)
# The first three of the week, then every other player.
RUNNER_GAINS = (10, 7, 5)
RUNNER_OTHER_GAIN = 2

# The score of the game in the browser (frontend/src/features/games/runner/engine.ts): one point
# per 10 pixels run, at a speed that starts at 300 pixels a second and never passes 900. So never
# more than 90 points a second, give or take the last frame.
MAX_POINTS_PER_SECOND = 90
SCORE_SLACK = 10


@dataclass(frozen=True)
class RunResult:
    member_id: uuid.UUID
    score: int
    finished_at: datetime


def max_score(duration_ms: int) -> int:
    return duration_ms * MAX_POINTS_PER_SECOND // 1000 + SCORE_SLACK


def plausible(score: int, duration_ms: int) -> bool:
    """A score the game could give in that time, for a run of 30 minutes at most."""
    longest = int(RUN_MAX.total_seconds() * 1000)
    return 0 <= duration_ms <= longest and 0 <= score <= max_score(duration_ms)


def rank_runner(runs: Iterable[RunResult]) -> list[RunResult]:
    """Each player's best run, best first; on a tie, the older run goes first."""
    best: dict[uuid.UUID, RunResult] = {}
    for run in runs:
        kept = best.get(run.member_id)
        if kept is None or (run.score, -run.finished_at.timestamp()) > (
            kept.score,
            -kept.finished_at.timestamp(),
        ):
            best[run.member_id] = run
    return sorted(best.values(), key=lambda r: (-r.score, r.finished_at))


def runner_gains(ranked: list[RunResult]) -> list[tuple[uuid.UUID, int]]:
    return [
        (run.member_id, RUNNER_GAINS[i] if i < len(RUNNER_GAINS) else RUNNER_OTHER_GAIN)
        for i, run in enumerate(ranked)
    ]


def week_to_pay(now: datetime) -> date:
    """The last week whose runs are all over: the one before this week once Monday's first 30
    minutes are past (a run started on Sunday evening may still finish), else the one before."""
    monday, _ = week_bounds(now)
    weeks_back = 1 if now >= monday + RUN_MAX else 2
    return week_start(now) - timedelta(days=7 * weeks_back)
