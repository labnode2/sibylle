import uuid
from datetime import date
from decimal import Decimal

import pytest

from sybille.domain.closest import closest
from sybille.domain.settlement import BetLine

pytestmark = pytest.mark.unit


def bet(value: Decimal | date, *, active: bool = True) -> BetLine:
    return BetLine(
        id=uuid.uuid4(), member_id=uuid.uuid4(), stake=10, rank=1, active=active, value=value
    )


def test_the_closest_number_wins() -> None:
    a, b, c = bet(Decimal("2")), bet(Decimal("4")), bet(Decimal("7"))
    assert closest([a, b, c], Decimal("3.4")) == {b.id}


def test_ties_all_win() -> None:
    a, b, c = bet(Decimal("2")), bet(Decimal("3")), bet(Decimal("4"))
    assert closest([a, b, c], Decimal("2.5")) == {a.id, b.id}


def test_hundredths_count() -> None:
    a, b, c = bet(Decimal("1.24")), bet(Decimal("1.26")), bet(Decimal("1.30"))
    assert closest([a, b, c], Decimal("1.25")) == {a.id, b.id}
    assert closest([a, b, c], Decimal("1.27")) == {b.id}


def test_negative_numbers() -> None:
    a, b = bet(Decimal("-3.50")), bet(Decimal("1"))
    assert closest([a, b], Decimal("-2")) == {a.id}


def test_the_exact_answer_wins_alone() -> None:
    a, b = bet(Decimal("12")), bet(Decimal("12.01"))
    assert closest([a, b], Decimal("12.00")) == {a.id}


def test_the_closest_date_wins() -> None:
    a, b, c = bet(date(2026, 12, 8)), bet(date(2026, 12, 9)), bet(date(2026, 12, 14))
    assert closest([a, b, c], date(2026, 12, 10)) == {b.id}


def test_dates_on_both_sides_tie() -> None:
    a, b = bet(date(2026, 12, 8)), bet(date(2026, 12, 12))
    assert closest([a, b], date(2026, 12, 10)) == {a.id, b.id}


def test_a_replaced_bet_never_wins() -> None:
    exact = bet(date(2026, 12, 10), active=False)
    far = bet(date(2027, 1, 30))
    assert closest([exact, far], date(2026, 12, 10)) == {far.id}


def test_no_bet_no_winner() -> None:
    assert closest([], Decimal("1")) == frozenset()
    assert closest([bet(Decimal("1"), active=False)], Decimal("1")) == frozenset()
