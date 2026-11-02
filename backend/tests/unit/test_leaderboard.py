from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from sybille.domain.leaderboard import (
    Period,
    Window,
    all_time,
    is_ranked,
    on_podium,
    rank,
    window,
)
from sybille.domain.ledger import purchase

pytestmark = pytest.mark.unit

PARIS = ZoneInfo("Europe/Paris")


def paris(*args: int) -> datetime:
    return datetime(*args, tzinfo=PARIS)


def test_the_month_is_the_paris_month() -> None:
    month = window(Period.MONTH, paris(2026, 11, 15, 12))
    assert (month.start, month.end) == (paris(2026, 11, 1), paris(2026, 12, 1))
    # 23:30 UTC on 30 November is already 00:30 on 1 December in Paris.
    assert not month.contains(datetime(2026, 11, 30, 23, 30, tzinfo=UTC))
    assert month.contains(datetime(2026, 10, 31, 23, 30, tzinfo=UTC))


def test_the_season_is_the_one_we_are_in() -> None:
    autumn = window(Period.SEASON, paris(2026, 12, 20, 23, 59))
    assert (autumn.start, autumn.end) == (paris(2026, 9, 23), paris(2026, 12, 21))
    winter = window(Period.SEASON, paris(2026, 12, 21, 0, 0, 30))
    assert (winter.start, winter.end) == (paris(2026, 12, 21), paris(2027, 3, 21))


def test_all_time_has_no_bounds() -> None:
    always = window(Period.ALL_TIME, paris(2026, 11, 15))
    assert always == Window(None, None)
    assert always.contains(paris(2001, 1, 1)) and always.contains(paris(2099, 1, 1))


def test_ties_share_a_rank_and_the_next_rank_is_skipped() -> None:
    standings = rank([("Cami", 50), ("Léo", 50), ("Manon", 20), ("Zoé", 20), ("Inès", -10)])
    assert [(s.key, s.rank, s.value) for s in standings] == [
        ("Cami", 1, 50),
        ("Léo", 1, 50),
        ("Manon", 3, 20),
        ("Zoé", 3, 20),
        ("Inès", 5, -10),
    ]


def test_ranking_keeps_the_given_order_within_a_tie() -> None:
    standings = rank([("Zoé", 0), ("Cami", 10), ("Ali", 0)])
    assert [s.key for s in standings] == ["Cami", "Zoé", "Ali"]
    assert rank([]) == []


def test_only_active_members_are_ranked() -> None:
    assert is_ranked("active")
    assert not is_ranked("left")
    assert not is_ranked("anonymized")


def test_all_time_adds_the_engraved_scores_to_the_open_seasons() -> None:
    assert all_time([50, -10, 30], 12) == 82
    assert all_time([], 0) == 0


def test_the_podium_is_the_first_three_ranks() -> None:
    assert [on_podium(r) for r in (1, 2, 3, 4)] == [True, True, True, False]
    # Two members tied third are both on the podium.
    standings = rank([("a", 9), ("b", 8), ("c", 7), ("d", 7), ("e", 1)])
    assert [on_podium(s.rank) for s in standings] == [True, True, True, True, False]


def test_a_purchase_leaves_the_score_alone() -> None:
    effect = purchase(30)
    assert (effect.amount, effect.score_delta) == (-30, 0)
