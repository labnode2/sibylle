"""Rules of the mini-games: the ball's race (research.md J3 and R19), Pixel mystère (J4) and
Wordle."""

import hashlib
import random
import re
import secrets
import unicodedata
import uuid
from collections import Counter
from collections.abc import Callable, Container, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sibylle.domain.seasons import PARIS, week_bounds, week_start
from sibylle.domain.wordle_words import ANSWERS, WordLists

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
# The words of a drawing, the main one included.
WORDS_MAX = 5


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


# Wordle: each newsroom has its word of the day, drawn from the word file's answers
# (domain/wordle_words.py) as its level allows, and kept.

WORDLE_LETTERS = 5
WORDLE_TRIES = 6
# A word of this level or more, among the rarer ones, gives whoever missed it six times a last
# chance: its letters in alphabetical order, and a seventh try, which pays nothing.
WORDLE_LAST_CHANCE_LEVEL = 4
Mark = Literal["correct", "present", "absent"]
# A newsroom's level, 1 Facile, 2 Normal or 3 Difficile: how many tiers of the word file, from
# the most common, its words come from (None: all of them). Normal until the editor chooses.
WORDLE_LEVEL_TIERS: dict[int, int | None] = {1: 2, 2: 4, 3: None}
WORDLE_DEFAULT_LEVEL = 2
# Once a newsroom had every word its level allows, a word comes back only if it was not out in
# this many days before.
WORDLE_REPEAT_DAYS = 100


def wordle_answer(day: date) -> str:
    """The word every newsroom shared on a day (Paris) before each drew its own: picked from the
    answers written by hand by a hash of the date. It stays the word of a newsroom whose members
    had begun that day's game before its own word was drawn, the day the draw came in."""
    digest = hashlib.sha256(f"sibylle-wordle:{day.isoformat()}".encode()).digest()
    return ANSWERS[int.from_bytes(digest[:8], "big") % len(ANSWERS)]


def wordle_level(lists: WordLists, word: str) -> int | None:
    """A word's level: the rank of its tier in the file, from 1 for the first (the most common
    words), whatever the tiers are called; None for the lists written by hand, or a word in no
    tier."""
    if not lists.levelled:
        return None
    return next((rank for rank, tier in enumerate(lists.tiers, start=1) if word in tier), None)


def wordle_allowed(lists: WordLists, newsroom_level: int) -> tuple[str, ...]:
    """The words a newsroom's level allows, those of its first tiers; with the lists written by
    hand, every answer."""
    count = WORDLE_LEVEL_TIERS[newsroom_level] if lists.levelled else None
    return tuple(word for tier in lists.tiers[:count] for word in tier)


def wordle_pick(
    allowed: Sequence[str],
    history: Iterable[tuple[date, str]],
    day: date,
    choose: Callable[[Sequence[str]], str] = secrets.choice,
) -> str:
    """A newsroom's word of `day`, drawn at random among the allowed words it never had (its
    `history`: the day and word of each of its days); once it had them all, among those not out
    in the 100 days before; and when none is left, the one out the longest ago. `allowed` is
    never empty."""
    last: dict[str, date] = {}
    for when, word in history:
        if word not in last or when > last[word]:
            last[word] = when
    never = [word for word in allowed if word not in last]
    if never:
        return choose(never)
    since = day - timedelta(days=WORDLE_REPEAT_DAYS)
    rested = [word for word in allowed if last[word] < since]
    if rested:
        return choose(rested)
    return min(allowed, key=lambda word: last[word])


def wordle_word(text: str, guesses: Container[str], answer: str) -> str | None:
    """The word tried, normalized, if it may be tried: one of the `guesses`, or the word of the
    day itself, which may be missing from them; else None."""
    word = normalize_word(text)
    if len(word) != WORDLE_LETTERS:
        return None
    return word if word == answer or word in guesses else None


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


def wordle_tries(level: int | None) -> int:
    """How many tries a word gives: six, and the last chance's seventh from level 4 on; never
    for a word without a level."""
    if level is not None and level >= WORDLE_LAST_CHANCE_LEVEL:
        return WORDLE_TRIES + 1
    return WORDLE_TRIES


def wordle_hint(word: str) -> str:
    """The last chance's hint: the word's letters in capitals and in alphabetical order, between
    spaces, a double letter twice. « matin » gives « A I M N T », « belle » « B E E L L »."""
    return " ".join(sorted(word.upper()))


def wordle_gain(tries: int) -> int:
    """6 laurels for a word found at the first try, then 5, 4, 3, 2 and 1 for the sixth; nothing
    at the last chance, the seventh."""
    return max(WORDLE_TRIES + 1 - tries, 0)
