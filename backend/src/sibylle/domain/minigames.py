"""Rules of the mini-games: the ball's race (research.md J3 and R19) and Pixel mystère (J4)."""

import math
import random
import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sibylle.domain.seasons import PARIS, week_bounds, week_start

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


# Pixel mystère

PIXEL_GUESSES_PER_DAY = 3
PIXEL_GAINS = (10, 7, 5)
PIXEL_OTHER_GAIN = 3
# A seventh of the pixels shows each morning at 08:00 (Paris), the first batch at the opening.
REVEAL_DAYS = 7
REVEAL_HOUR = 8
# The value of a pixel not shown yet, in the drawing sent to the players.
HIDDEN = 255
WORD = re.compile(r"^[^\W\d_]+(?:[ '’-][^\W\d_]+)*$")
WORD_MAX = 24


def normalize_word(text: str) -> str:
    """Lower case, no accents, single spaces: « Tour  Eiffel » and « tour eiffel » match."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return " ".join(stripped.casefold().split())


def valid_word(text: str) -> bool:
    """Letters, possibly in several words joined by spaces, hyphens or apostrophes."""
    word = " ".join(text.split())
    return 2 <= letter_count(word) and len(word) <= WORD_MAX and bool(WORD.match(word))


def letter_count(word: str) -> int:
    return sum(1 for c in word if c.isalpha())


def reveal_order(size: int, rng: random.Random | None = None) -> bytes:
    """Every pixel of the drawing in a random order, two bytes each."""
    order = list(range(size * size))
    (rng or random.SystemRandom()).shuffle(order)
    return b"".join(i.to_bytes(2, "big") for i in order)


def order_indices(order: bytes) -> list[int]:
    return [int.from_bytes(order[i : i + 2], "big") for i in range(0, len(order), 2)]


def batch_size(size: int) -> int:
    return math.ceil(size * size / REVEAL_DAYS)


def _morning(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, REVEAL_HOUR, tzinfo=PARIS)


def mornings_between(start: datetime, now: datetime) -> int:
    """How many 08:00 (Paris) passed after `start`, up to `now` included."""
    first_day = start.astimezone(PARIS).date()
    if _morning(first_day) <= start:
        first_day += timedelta(days=1)
    last_day = now.astimezone(PARIS).date()
    if _morning(last_day) > now:
        last_day -= timedelta(days=1)
    return max(0, (last_day - first_day).days + 1)


def revealed_count(size: int, started_at: datetime, now: datetime) -> int:
    batches = 1 + mornings_between(started_at, now)
    return min(size * size, batches * batch_size(size))


def reveal_end(size: int, started_at: datetime) -> datetime:
    """The morning the last pixels show, which ends the drawing (unless everyone finds it
    first): the opening shows the first batch, each 08:00 after it the next one."""
    mornings = math.ceil(size * size / batch_size(size)) - 1
    if mornings <= 0:
        return started_at
    first_day = started_at.astimezone(PARIS).date()
    if _morning(first_day) <= started_at:
        first_day += timedelta(days=1)
    return _morning(first_day + timedelta(days=mornings - 1))


def masked(pixels: bytes, order: bytes, count: int) -> bytes:
    """The drawing with only its first `count` pixels in the reveal order; the others HIDDEN."""
    shown = bytearray([HIDDEN]) * len(pixels)
    for index in order_indices(order)[:count]:
        shown[index] = pixels[index]
    return bytes(shown)


def pixel_gain(rank: int) -> int:
    return PIXEL_GAINS[rank - 1] if rank <= len(PIXEL_GAINS) else PIXEL_OTHER_GAIN


def next_start(finished_at: datetime) -> datetime:
    """The next drawing starts the day after the last one ended, at 08:00."""
    return _morning(finished_at.astimezone(PARIS).date() + timedelta(days=1))
