"""Wordle: the colours of a try, the word file and its checks, the levels, the draw of a
newsroom's word, the words a try may be, the gain, the last chance of a rarer word."""

import json
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import pytest
from tests.wordle_sample import PER_TIER, TIERS, encoded, sample, tier_words, word, words_of

from sibylle.domain.minigames import (
    WORDLE_LETTERS,
    wordle_allowed,
    wordle_answer,
    wordle_gain,
    wordle_hint,
    wordle_level,
    wordle_marks,
    wordle_pick,
    wordle_tries,
    wordle_word,
)
from sibylle.domain.wordle_words import (
    ACCEPTED,
    ANSWERS,
    OLD_LISTS,
    InvalidLists,
    WordLists,
    lists_from,
    parse_lists,
)

pytestmark = pytest.mark.unit

C, P, A = "correct", "present", "absent"
DAY = date(2026, 11, 28)


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


def test_the_shared_word_of_a_day_is_the_same_all_day_and_comes_from_the_old_answers() -> None:
    day = date(2026, 11, 15)
    assert wordle_answer(day) == wordle_answer(day)
    words = {wordle_answer(day + timedelta(days=i)) for i in range(60)}
    assert words <= set(ANSWERS)
    assert len(words) > 30


def test_the_old_lists_hold_five_letter_words_without_accents() -> None:
    assert all(len(w) == WORDLE_LETTERS and w.isascii() and w.islower() for w in ACCEPTED)
    assert len(set(ANSWERS)) == len(ANSWERS) >= 300
    assert set(ANSWERS) <= ACCEPTED


def test_a_word_tried_is_normalized_and_must_be_known() -> None:
    assert wordle_word("  ÉCOLE ", ACCEPTED, "table") == "ecole"
    assert wordle_word("zzzzz", ACCEPTED, "table") is None
    assert wordle_word("ecol", ACCEPTED, "table") is None
    assert wordle_word("écoles ", ACCEPTED, "table") is None


def test_the_word_of_the_day_may_be_tried_even_when_it_is_not_among_the_guesses() -> None:
    lists = parse_lists(encoded(sample()))
    assert "table" not in lists.guesses
    assert wordle_word("Table", lists.guesses, "table") == "table"
    assert wordle_word("table", lists.guesses, "arbre") is None


def test_the_gain_falls_from_six_to_one_laurel_and_the_last_chance_pays_nothing() -> None:
    assert [wordle_gain(tries) for tries in range(1, 8)] == [6, 5, 4, 3, 2, 1, 0]


# The last chance


def test_a_word_of_level_4_or_more_gives_a_seventh_try() -> None:
    assert [wordle_tries(level) for level in (1, 2, 3, 4, 5, 6)] == [6, 6, 6, 7, 7, 7]
    # A word of the lists written by hand has no level, and no last chance.
    assert wordle_tries(None) == 6


def test_the_hint_gives_the_letters_in_alphabetical_order() -> None:
    assert wordle_hint("matin") == "A I M N T"
    assert wordle_hint("arbre") == "A B E R R"


def test_the_hint_gives_a_double_letter_twice() -> None:
    assert wordle_hint("belle") == "B E E L L"
    assert wordle_hint("ebene") == "B E E E N"
    assert wordle_hint("aaaaa") == "A A A A A"


# The word file


def refused(data: dict[str, Any] | bytes, reason: str) -> None:
    with pytest.raises(InvalidLists, match=reason):
        parse_lists(data if isinstance(data, bytes) else encoded(data))


def test_a_good_file_is_taken_with_its_tiers_in_order() -> None:
    lists = parse_lists(encoded(sample()))
    assert len(lists.tiers) == TIERS
    assert lists.tiers[0] == tuple(tier_words(1))
    assert lists.tiers[-1] == tuple(tier_words(6))
    assert len(lists.guesses) == 1_000
    assert lists.levelled
    # The same once stored and read back as JSON.
    assert lists_from(json.loads(encoded(sample()))) == lists


def test_a_broken_file_is_refused() -> None:
    refused(b'{"answers": [{"id": "50+", "words": [', "not JSON")
    refused(b"\xff\xfe\x00garbage", "not JSON")
    refused(b"[1, 2, 3]", "not a JSON object")
    refused({"guesses": sample()["guesses"]}, "answers")
    refused({"answers": sample()["answers"]}, "guesses")


def test_a_word_of_six_letters_is_refused() -> None:
    data = sample()
    data["answers"][2]["words"][4]["word"] = "abcdef"
    refused(data, r"answers\[2\]\.words\[4\]: 'abcdef' is not five letters")
    data = sample()
    data["guesses"].append("abcdef")
    refused(data, "'abcdef' is not five letters")


def test_letters_beyond_a_to_z_are_refused() -> None:
    for wrong in ("ABCDE", "écran", "ab de", "abc1e", "cœurs"):
        data = sample()
        data["guesses"][10] = wrong
        refused(data, "is not five letters from a to z")


def test_an_answer_missing_from_the_guesses_is_refused() -> None:
    data = sample()
    data["guesses"].remove(word(3, 7))
    refused(data, f"'{word(3, 7)}' is not among the guesses")


def test_a_file_too_small_is_refused() -> None:
    data = sample()
    for tier in data["answers"]:
        tier["words"] = tier["words"][:16]
        tier["count"] = 16
    refused(data, "answers: 96 words, 100 at least")
    data = sample()
    # The last guess, in alphabetical order, is no answer.
    data["guesses"] = data["guesses"][:999]
    refused(data, "guesses: 999 words, 1000 at least")


def test_a_tier_out_of_the_format_is_refused() -> None:
    data = sample()
    data["answers"][1]["count"] = PER_TIER + 1
    refused(data, r"answers\[1\]: count 21 for 20 words")
    data = sample()
    del data["answers"][0]["min"]
    refused(data, r"answers\[0\]: not a tier")
    data = sample()
    data["answers"][0]["words"][0]["freq"] = "souvent"
    refused(data, r"answers\[0\]\.words\[0\]: its spelling, freq or kind")
    data = sample()
    data["answers"][5]["words"] = []
    data["answers"][5]["count"] = 0
    refused(data, r"answers\[5\]: no words")
    data = sample()
    data["answers"][4]["words"].append(data["answers"][0]["words"][0])
    data["answers"][4]["count"] += 1
    refused(data, "answers: 'aaaaa' twice")
    data = sample()
    data["answers"].append(dict(data["answers"][0], id="en trop"))
    refused(data, "7 tiers, 6 at most")


def test_a_level_is_the_rank_of_the_tier_whatever_its_name() -> None:
    lists = parse_lists(encoded(sample()))
    assert [wordle_level(lists, word(tier)) for tier in range(1, 7)] == [1, 2, 3, 4, 5, 6]
    assert wordle_level(lists, "zaaaa") is None
    # Other names, other bounds, the tiers in another order: their place makes the level.
    data = sample()
    data["answers"].reverse()
    for tier in data["answers"]:
        tier["id"], tier["min"], tier["max"] = "même nom", 0, None
    renamed = parse_lists(encoded(data))
    assert wordle_level(renamed, word(6)) == 1
    assert wordle_level(renamed, word(1)) == 6
    # Fewer tiers: still their place.
    data = sample()
    del data["answers"][5:]
    fewer = parse_lists(encoded(data))
    assert [wordle_level(fewer, word(tier)) for tier in range(1, 7)] == [1, 2, 3, 4, 5, None]


def test_a_newsroom_level_allows_the_first_two_four_or_all_tiers() -> None:
    lists = parse_lists(encoded(sample()))
    assert set(wordle_allowed(lists, 1)) == words_of(1, 2)
    assert set(wordle_allowed(lists, 2)) == words_of(1, 2, 3, 4)
    assert set(wordle_allowed(lists, 3)) == words_of(1, 2, 3, 4, 5, 6)
    # With three tiers only, Normal and Difficile take them all.
    three = WordLists(lists.tiers[:3], lists.guesses)
    assert set(wordle_allowed(three, 2)) == set(wordle_allowed(three, 3)) == words_of(1, 2, 3)


def test_the_old_lists_allow_every_answer_without_a_level() -> None:
    for newsroom_level in (1, 2, 3):
        assert wordle_allowed(OLD_LISTS, newsroom_level) == ANSWERS
    assert wordle_level(OLD_LISTS, ANSWERS[0]) is None
    assert OLD_LISTS.guesses == ACCEPTED


# The draw


def first(words: Sequence[str]) -> str:
    return words[0]


def test_the_draw_takes_a_word_never_out_while_there_are_some() -> None:
    allowed = tier_words(1)
    history = [(DAY - timedelta(days=400 + i), w) for i, w in enumerate(allowed[:-3])]
    assert {wordle_pick(allowed, history, DAY) for _ in range(200)} == set(allowed[-3:])
    assert wordle_pick(allowed, history, DAY, first) == allowed[-3]
    # A word out once, however long ago, waits while some never were.
    longer = [*history, (DAY - timedelta(days=999), allowed[-1])]
    assert {wordle_pick(allowed, longer, DAY) for _ in range(100)} == set(allowed[-3:-1])


def test_once_all_were_out_the_draw_skips_those_of_the_last_100_days() -> None:
    allowed = ["aaaaa", "aaaab", "aaaac", "aaaad"]
    history = [
        (DAY - timedelta(days=300), "aaaaa"),
        (DAY - timedelta(days=101), "aaaab"),
        (DAY - timedelta(days=100), "aaaac"),
        (DAY - timedelta(days=1), "aaaad"),
        # Out long ago, but again since.
        (DAY - timedelta(days=500), "aaaad"),
    ]
    picks = {wordle_pick(allowed, history, DAY) for _ in range(100)}
    assert picks == {"aaaaa", "aaaab"}


def test_with_every_word_out_lately_the_draw_takes_the_one_out_the_longest_ago() -> None:
    allowed = ["aaaaa", "aaaab", "aaaac"]
    history = [
        (DAY - timedelta(days=3), "aaaaa"),
        (DAY - timedelta(days=50), "aaaab"),
        (DAY - timedelta(days=2), "aaaac"),
    ]
    assert wordle_pick(allowed, history, DAY) == "aaaab"
