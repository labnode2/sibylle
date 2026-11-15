"""Wordle: the colours of a try, the word of a day, the gain."""

from datetime import date, timedelta

import pytest

from sibylle.domain.minigames import (
    WORDLE_LETTERS,
    wordle_answer,
    wordle_gain,
    wordle_marks,
    wordle_word,
)
from sibylle.domain.wordle_words import ACCEPTED, ANSWERS

pytestmark = pytest.mark.unit

C, P, A = "correct", "present", "absent"


def test_every_letter_in_place_is_green() -> None:
    assert wordle_marks("arbre", "arbre") == [C] * 5


def test_letters_elsewhere_are_yellow_and_the_others_grey() -> None:
    assert wordle_marks("livre", "reste") == [A, A, A, P, C]
    assert wordle_marks("abcde", "vwxyz") == [A] * 5


def test_a_double_letter_tried_once_in_the_answer_marks_one_only() -> None:
    # « allee » against « table »: the first l is in the word, the second has no l left, and the
    # last e, in place, is green.
    assert wordle_marks("allee", "table") == [P, P, A, A, C]
    # « lilas » against « lampe »: one l only in the answer, and the first is the one in place.
    assert wordle_marks("lilas", "lampe") == [C, A, A, P, A]


def test_a_green_takes_the_letter_before_a_yellow() -> None:
    # « ebene » has three e. The e in place take theirs first; a third e is yellow, a fourth not.
    assert wordle_marks("eerie", "ebene") == [C, P, A, A, C]
    assert wordle_marks("geese", "ebene") == [A, P, C, A, C]
    assert wordle_marks("eeeee", "ebene") == [C, A, C, A, C]


def test_a_double_letter_in_the_answer_shows_twice() -> None:
    assert wordle_marks("xxexe", "ebene") == [A, A, C, A, C]
    assert wordle_marks("xexxx", "ebene") == [A, P, A, A, A]


def test_the_word_of_a_day_is_the_same_all_day_and_comes_from_the_answers() -> None:
    day = date(2026, 11, 15)
    assert wordle_answer(day) == wordle_answer(day)
    words = {wordle_answer(day + timedelta(days=i)) for i in range(60)}
    assert words <= set(ANSWERS)
    assert len(words) > 30


def test_the_lists_hold_five_letter_words_without_accents() -> None:
    assert all(len(w) == WORDLE_LETTERS and w.isascii() and w.islower() for w in ACCEPTED)
    assert len(set(ANSWERS)) == len(ANSWERS) >= 300
    assert set(ANSWERS) <= ACCEPTED


def test_a_word_tried_is_normalized_and_must_be_known() -> None:
    assert wordle_word("  ÉCOLE ") == "ecole"
    assert wordle_word("zzzzz") is None
    assert wordle_word("ecol") is None
    assert wordle_word("écoles ") is None


def test_the_gain_falls_from_six_to_one_laurel() -> None:
    assert [wordle_gain(tries) for tries in range(1, 7)] == [6, 5, 4, 3, 2, 1]
