"""Pixel mystère (research.md J4)."""

import random
from datetime import datetime, timedelta

import pytest

from sibylle.domain.minigames import (
    HIDDEN,
    PIXEL_DURATION,
    PIXEL_GUESSES_PER_DAY,
    letter_count,
    masked,
    next_start,
    normalize_word,
    order_indices,
    pixel_gain,
    reveal_end,
    reveal_order,
    revealed_count,
)
from sibylle.domain.seasons import PARIS

pytestmark = pytest.mark.unit

WEDNESDAY = datetime(2026, 11, 4, 15, 0, tzinfo=PARIS)


def test_the_reveal_order_is_drawn_once_over_every_pixel() -> None:
    for size in (16, 32):
        order = order_indices(reveal_order(size, random.Random(1)))
        assert sorted(order) == list(range(size * size))
    assert reveal_order(16, random.Random(1)) != reveal_order(16, random.Random(2))


def test_pixels_show_in_proportion_to_the_time_gone() -> None:
    def shown(fraction: float, size: int = 16) -> int:
        return revealed_count(size, WEDNESDAY, WEDNESDAY + PIXEL_DURATION * fraction)

    assert (shown(0), shown(0.5), shown(1)) == (0, 128, 256)
    assert (shown(0, 32), shown(0.5, 32), shown(1, 32)) == (0, 512, 1024)
    # Rounded up, and never more than the drawing, nor less than nothing.
    assert shown(0.001) == 1
    assert shown(3) == 256
    assert revealed_count(16, WEDNESDAY, WEDNESDAY - timedelta(hours=1)) == 0


def test_the_drawing_ends_a_week_after_its_opening() -> None:
    end = reveal_end(WEDNESDAY)
    assert end == WEDNESDAY + timedelta(days=7)
    assert revealed_count(16, WEDNESDAY, end - timedelta(hours=1)) < 256
    assert revealed_count(16, WEDNESDAY, end) == 256


def test_pixels_follow_the_clock_not_the_morning() -> None:
    saturday = datetime(2026, 10, 24, 10, 0, tzinfo=PARIS)  # summer time ends on Sunday 25
    assert revealed_count(16, saturday, saturday + timedelta(days=1)) == 37


def test_hidden_pixels_stay_hidden() -> None:
    drawing = bytes(range(16)) * 16
    order = reveal_order(16, random.Random(3))
    shown = masked(drawing, order, 37)
    first = set(order_indices(order)[:37])
    assert [i for i, value in enumerate(shown) if value != HIDDEN] == sorted(first)
    assert all(shown[i] == drawing[i] for i in first)
    assert masked(drawing, order, 256) == drawing


@pytest.mark.parametrize(
    ("guess", "word"),
    [
        ("cafe", "Café"),
        ("  CAFÉ ", "café"),
        ("tour   eiffel", "Tour Eiffel"),
        ("Éléphant", "elephant"),
    ],
)
def test_case_accents_and_extra_spaces_do_not_count(guess: str, word: str) -> None:
    assert normalize_word(guess) == normalize_word(word)


def test_letters_are_counted_without_spaces_or_signs() -> None:
    assert letter_count("Tour Eiffel") == 10
    assert letter_count("aujourd'hui") == 10
    assert letter_count("porte-monnaie") == 12


def test_the_gain_falls_from_fifty_to_three_whatever_the_rank() -> None:
    assert pixel_gain(timedelta(0)) == 50
    assert pixel_gain(PIXEL_DURATION / 2) == 26  # 26.5 laurels: the half goes to the finder's loss
    assert pixel_gain(PIXEL_DURATION) == 3
    # The floor holds after the end, and before the opening nothing is lost.
    assert pixel_gain(PIXEL_DURATION * 2) == 3
    assert pixel_gain(-PIXEL_DURATION) == 50
    gains = [pixel_gain(PIXEL_DURATION * i / 100) for i in range(101)]
    assert gains == sorted(gains, reverse=True)
    assert PIXEL_GUESSES_PER_DAY == 3


def test_two_finds_at_the_same_moment_win_the_same() -> None:
    at = timedelta(days=2, hours=5)
    assert pixel_gain(at) == pixel_gain(at)
    assert pixel_gain(at) == 35  # 50 - 14.8


def test_the_next_drawing_starts_the_next_morning() -> None:
    assert next_start(WEDNESDAY) == datetime(2026, 11, 5, 8, 0, tzinfo=PARIS)
    early = datetime(2026, 11, 4, 7, 0, tzinfo=PARIS)
    assert next_start(early) == datetime(2026, 11, 5, 8, 0, tzinfo=PARIS)
    assert next_start(WEDNESDAY) - WEDNESDAY == timedelta(hours=17)
