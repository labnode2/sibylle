"""Rules of the mini-games: the ball's race (research.md J3 and R19) and Pixel mystère (J4)."""

import hashlib
import random
import re
import unicodedata
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sibylle.domain.seasons import PARIS, week_bounds, week_start
from sibylle.domain.wordle_words import ACCEPTED, ANSWERS

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
# A drawing lasts a week: its pixels show in proportion to the time gone, and what finding the
# word pays falls the same way, from 50 laurels at the opening to 3 at the end, whatever the rank.
REVEAL_DAYS = 7
PIXEL_DURATION = timedelta(days=REVEAL_DAYS)
PIXEL_START_GAIN = 50
PIXEL_OTHER_GAIN = 3
# What a drawing pays its author: once when it goes live, then at each find.
PIXEL_AUTHOR_BONUS = 25
PIXEL_AUTHOR_PER_FIND = 5
# The next drawing starts at this hour (Paris), the day after the last one ended.
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


def _micros(delta: timedelta) -> int:
    return delta // timedelta(microseconds=1)


def revealed_count(
    size: int, started_at: datetime, now: datetime, duration: timedelta = PIXEL_DURATION
) -> int:
    """The pixels shown `now`: `ceil(total × elapsed / duration)`, none before the opening."""
    elapsed = min(max(_micros(now - started_at), 0), _micros(duration))
    return -(-size * size * elapsed // _micros(duration))


def reveal_end(started_at: datetime, duration: timedelta = PIXEL_DURATION) -> datetime:
    """When the last pixels show, which ends the drawing (unless everyone finds it first)."""
    return started_at + duration


def masked(pixels: bytes, order: bytes, count: int) -> bytes:
    """The drawing with only its first `count` pixels in the reveal order; the others HIDDEN."""
    shown = bytearray([HIDDEN]) * len(pixels)
    for index in order_indices(order)[:count]:
        shown[index] = pixels[index]
    return bytes(shown)


def pixel_gain(elapsed: timedelta, duration: timedelta = PIXEL_DURATION) -> int:
    """What finding the word pays after `elapsed`: 50 laurels at the opening, falling in a line
    to 3 at the end of `duration`, rounded to the whole laurel. The same for all at that moment."""
    done = min(max(_micros(elapsed), 0), _micros(duration))
    span = PIXEL_START_GAIN - PIXEL_OTHER_GAIN
    return PIXEL_START_GAIN - (span * done * 2 + _micros(duration)) // (2 * _micros(duration))


def _morning(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, REVEAL_HOUR, tzinfo=PARIS)


def next_start(finished_at: datetime) -> datetime:
    """The next drawing starts the day after the last one ended, at 08:00."""
    return _morning(finished_at.astimezone(PARIS).date() + timedelta(days=1))


# Wordle

WORDLE_LETTERS = 5
WORDLE_TRIES = 6
Mark = Literal["correct", "present", "absent"]


def wordle_answer(day: date) -> str:
    """The word of a day (Paris): the same for all, picked from the answers by a hash of the date,
    so that nothing about tomorrow's word shows in today's."""
    digest = hashlib.sha256(f"sibylle-wordle:{day.isoformat()}".encode()).digest()
    return ANSWERS[int.from_bytes(digest[:8], "big") % len(ANSWERS)]


def wordle_word(text: str) -> str | None:
    """The word tried, normalized, if it is one that is accepted; else None."""
    word = normalize_word(text)
    return word if len(word) == WORDLE_LETTERS and word in ACCEPTED else None


def wordle_marks(guess: str, answer: str) -> list[Mark]:
    """Each letter of `guess`: `correct` in its place, `present` elsewhere in the answer, else
    `absent`. A letter is marked as many times as the answer has it: the greens first, then the
    yellows from the left, so a double letter tried once in the answer shows one yellow only."""
    marks: list[Mark] = ["absent"] * len(guess)
    left = Counter(a for g, a in zip(guess, answer, strict=True) if g != a)
    for i, (g, a) in enumerate(zip(guess, answer, strict=True)):
        if g == a:
            marks[i] = "correct"
        elif left[g] > 0:
            marks[i] = "present"
            left[g] -= 1
    return marks


def wordle_gain(tries: int) -> int:
    """6 laurels for a word found at the first try, then 5, 4, 3, 2 and 1 for the sixth."""
    return WORDLE_TRIES + 1 - tries
