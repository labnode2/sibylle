"""Wordle: the colours of a try, the word file and its checks, the levels, the draw of a
newsroom's word, the words a try may be, the gain, the last chance of a rarer word, the chain of
wins with its joker and its bonus, the ranking of the day."""

import json
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from tests.wordle_sample import PER_TIER, TIERS, encoded, sample, tier_words, word, words_of

from sibylle.domain.minigames import (
    WORDLE_LETTERS,
    WordleResult,
    WordleStreak,
    rank_wordle,
    wordle_allowed,
    wordle_answer,
    wordle_gain,
    wordle_hint,
    wordle_level,
    wordle_marks,
    wordle_pick,
    wordle_stage,
    wordle_streak,
    wordle_tries,
    wordle_word,
)
from sibylle.domain.seasons import PARIS
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


def test_the_gain_falls_from_32_laurels_to_1_and_the_last_chance_pays_nothing() -> None:
    assert [wordle_gain(tries) for tries in range(1, 8)] == [32, 8, 6, 4, 2, 1, 0]


# The chain of wins

STATES = {"W": "won", "L": "lost", "P": "playing"}


def played(pattern: str, start: date = DAY) -> dict[date, str]:
    """A member's games, a letter a day from `start`: W won, L lost, P begun and never finished,
    and a dot for a day without a game."""
    return {start + timedelta(days=i): STATES[c] for i, c in enumerate(pattern) if c != "."}


def chain(pattern: str) -> WordleStreak:
    """The chain on the day after those days, before its game: each of them is over."""
    return wordle_streak(played(pattern), DAY + timedelta(days=len(pattern)))


def test_each_day_won_adds_one_to_the_chain() -> None:
    assert chain("") == WordleStreak(0, joker=False)
    assert [chain("W" * days).current for days in range(1, 8)] == [1, 2, 3, 4, 5, 6, 7]
    # Whatever the days before the first game: the chain counts from it.
    assert wordle_streak(played("WW", DAY + timedelta(days=30)), DAY + timedelta(days=32)) == (
        WordleStreak(2, joker=False)
    )


def test_a_day_missed_from_3_takes_the_joker_then_the_next_one_sends_the_chain_back_to_0() -> None:
    assert chain("WWW") == WordleStreak(3, joker=True)
    assert chain("WWWL") == WordleStreak(3, joker=False)
    assert chain("WWWLW") == WordleStreak(4, joker=False)
    # The second miss of the same stage, from 3 to 8: no joker left.
    assert chain("WWWLL") == WordleStreak(0, joker=False)
    assert chain("WWWWWLWWL") == WordleStreak(0, joker=False)
    assert chain("WWWWWLWWLW") == WordleStreak(1, joker=False)


def test_below_3_a_day_missed_sends_the_chain_back_to_0() -> None:
    assert chain("WW") == WordleStreak(2, joker=False)
    assert chain("WWL") == WordleStreak(0, joker=False)
    assert chain("WL") == WordleStreak(0, joker=False)
    assert chain("L") == WordleStreak(0, joker=False)


def test_a_day_without_a_game_or_with_a_game_not_finished_is_a_day_missed() -> None:
    assert chain("WW.W") == WordleStreak(1, joker=False)
    assert chain("WWW.W") == WordleStreak(4, joker=False)
    assert chain("WWW..W") == WordleStreak(1, joker=False)
    assert chain("WWWPW") == WordleStreak(4, joker=False)
    assert chain("WWWPP") == WordleStreak(0, joker=False)


def test_the_joker_comes_back_at_each_new_power_of_3() -> None:
    # Used from 3 to 8, back at 9.
    used = "WWWL"
    assert chain(used + "W" * 5) == WordleStreak(8, joker=False)
    assert chain(used + "W" * 6) == WordleStreak(9, joker=True)
    assert chain(used + "W" * 6 + "L") == WordleStreak(9, joker=False)
    assert chain(used + "W" * 6 + "LL") == WordleStreak(0, joker=False)
    # Used at 9, back at 27.
    used = "W" * 9 + "L"
    assert chain(used + "W" * 17) == WordleStreak(26, joker=False)
    assert chain(used + "W" * 18) == WordleStreak(27, joker=True)
    # And so on without end: used at 81, back at 243.
    used = "W" * 81 + "L"
    assert chain(used + "W" * 161) == WordleStreak(242, joker=False)
    assert chain(used + "W" * 162) == WordleStreak(243, joker=True)
    assert chain(used + "W" * 162 + "L") == WordleStreak(243, joker=False)


def test_a_joker_not_used_does_not_add_up_with_the_next_one() -> None:
    assert chain("W" * 9) == WordleStreak(9, joker=True)
    assert chain("W" * 9 + "L") == WordleStreak(9, joker=False)
    assert chain("W" * 9 + "LL") == WordleStreak(0, joker=False)


def test_today_counts_only_once_its_game_is_over() -> None:
    days = played("WWW")
    today = DAY + timedelta(days=3)
    # Not played yet, or begun: the chain of last evening.
    assert wordle_streak(days, today) == WordleStreak(3, joker=True)
    assert wordle_streak(days | {today: "playing"}, today) == WordleStreak(3, joker=True)
    assert wordle_streak(days | {today: "won"}, today) == WordleStreak(4, joker=True)
    assert wordle_streak(days | {today: "lost"}, today) == WordleStreak(3, joker=False)
    # The next day, a game left unfinished was a day missed.
    tomorrow = today + timedelta(days=1)
    assert wordle_streak(days | {today: "playing"}, tomorrow) == WordleStreak(3, joker=False)
    # Two days missed in a row: the joker took the first.
    assert wordle_streak(days, tomorrow + timedelta(days=1)) == WordleStreak(0, joker=False)


def test_the_flame_shows_from_two_wins_though_the_bonus_and_the_joker_wait_for_3() -> None:
    assert not chain("W").shown
    assert (chain("WW").shown, chain("WW").joker, chain("WW").bonus) == (True, False, 0)
    assert (chain("WWW").shown, chain("WWW").joker, chain("WWW").bonus) == (True, True, 1)


def test_the_bonus_is_the_rank_of_the_chains_stage_without_end() -> None:
    bonus = {chain: WordleStreak(chain, joker=False).bonus for chain in range(0, 800)}
    assert [bonus[chain] for chain in (0, 1, 2)] == [0, 0, 0]
    assert {bonus[chain] for chain in range(3, 9)} == {1}
    assert [bonus[9], bonus[26], bonus[27], bonus[80], bonus[81]] == [2, 2, 3, 3, 4]
    assert [bonus[100], bonus[242], bonus[243], bonus[300], bonus[728], bonus[729]] == [
        4,
        4,
        5,
        5,
        5,
        6,
    ]
    # In integers: right at each power of 3, however far.
    assert [wordle_stage(3**rank) for rank in range(1, 40)] == list(range(1, 40))
    assert [wordle_stage(3**rank - 1) for rank in range(1, 40)] == list(range(0, 39))


# The ranking of the day


def test_the_ranking_puts_the_fewest_tries_first_then_the_first_to_find_then_who_lost() -> None:
    def at(minutes: int) -> datetime:
        return datetime(2026, 11, 28, 8, 0, tzinfo=PARIS) + timedelta(minutes=minutes)

    two = WordleResult(uuid.uuid4(), won=True, tries=2, finished_at=at(30))
    four_late = WordleResult(uuid.uuid4(), won=True, tries=4, finished_at=at(20))
    four_early = WordleResult(uuid.uuid4(), won=True, tries=4, finished_at=at(10))
    six = WordleResult(uuid.uuid4(), won=True, tries=6, finished_at=at(50))
    # Found at the last chance, the seventh try: after the sixth, however early.
    seventh = WordleResult(uuid.uuid4(), won=True, tries=7, finished_at=at(0))
    lost_late = WordleResult(uuid.uuid4(), won=False, tries=6, finished_at=at(40))
    lost_early = WordleResult(uuid.uuid4(), won=False, tries=7, finished_at=at(5))
    ranked = rank_wordle([lost_late, six, four_late, seventh, lost_early, two, four_early])
    assert ranked == [
        (1, two),
        (2, four_early),
        (3, four_late),
        (4, six),
        (5, seventh),
        (None, lost_early),
        (None, lost_late),
    ]
    assert rank_wordle([]) == []


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
