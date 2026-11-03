"""Pixel mystère (research.md J4)."""

import random
from datetime import datetime, timedelta

import pytest

from sibylle.domain.minigames import (
    HIDDEN,
    PIXEL_GUESSES_PER_DAY,
    batch_size,
    letter_count,
    masked,
    next_start,
    normalize_word,
    order_indices,
    pixel_gain,
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


def test_a_seventh_of_the_pixels_a_day() -> None:
    assert (batch_size(16), batch_size(32)) == (37, 147)


def test_the_first_batch_at_the_opening_then_one_each_morning_at_eight() -> None:
    def shown(at: datetime) -> int:
        return revealed_count(16, WEDNESDAY, at)

    assert shown(WEDNESDAY) == 37
    assert shown(datetime(2026, 11, 5, 7, 59, tzinfo=PARIS)) == 37
    assert shown(datetime(2026, 11, 5, 8, 0, tzinfo=PARIS)) == 74
    assert shown(datetime(2026, 11, 9, 8, 0, tzinfo=PARIS)) == 37 * 6
    # The seventh batch shows everything, and no more.
    assert shown(datetime(2026, 11, 10, 8, 0, tzinfo=PARIS)) == 256
    assert shown(datetime(2026, 11, 20, 8, 0, tzinfo=PARIS)) == 256


def test_eight_o_clock_stays_eight_o_clock_when_the_clocks_change() -> None:
    saturday = datetime(2026, 10, 24, 10, 0, tzinfo=PARIS)  # summer time ends on Sunday 25
    assert revealed_count(16, saturday, datetime(2026, 10, 26, 7, 59, tzinfo=PARIS)) == 74
    assert revealed_count(16, saturday, datetime(2026, 10, 26, 8, 0, tzinfo=PARIS)) == 111


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


def test_ten_seven_five_then_three() -> None:
    assert [pixel_gain(rank) for rank in range(1, 6)] == [10, 7, 5, 3, 3]
    assert PIXEL_GUESSES_PER_DAY == 3


def test_the_next_drawing_starts_the_next_morning() -> None:
    assert next_start(WEDNESDAY) == datetime(2026, 11, 5, 8, 0, tzinfo=PARIS)
    early = datetime(2026, 11, 4, 7, 0, tzinfo=PARIS)
    assert next_start(early) == datetime(2026, 11, 5, 8, 0, tzinfo=PARIS)
    assert next_start(WEDNESDAY) - WEDNESDAY == timedelta(hours=17)
