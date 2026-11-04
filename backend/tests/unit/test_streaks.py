import pytest

from sibylle.domain.streaks import SHOWN_FROM, Streak, streak

pytestmark = pytest.mark.unit

WON, LOST = True, False


def test_no_result_no_chain() -> None:
    assert streak([]) == Streak(current=0, best=0)


def test_wins_in_a_row_make_the_chain_and_the_record() -> None:
    assert streak([WON, WON, WON]) == Streak(current=3, best=3)


def test_a_loss_starts_the_chain_again() -> None:
    assert streak([WON, WON, WON, LOST, WON]) == Streak(current=1, best=3)
    assert streak([WON, WON, LOST]) == Streak(current=0, best=2)


def test_the_record_is_the_longest_chain_whenever_it_was() -> None:
    assert streak([LOST, WON, LOST, WON, WON, LOST, WON]) == Streak(current=1, best=2)
    assert streak([WON, WON, LOST, WON, WON, WON]) == Streak(current=3, best=3)


def test_a_single_win_is_not_yet_a_chain_to_show() -> None:
    assert SHOWN_FROM == 2
    assert not streak([WON]).shown
    assert streak([WON, WON]).shown
