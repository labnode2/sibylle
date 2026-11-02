from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from sybille.domain.betting import (
    Answer,
    BetRefused,
    Kind,
    PronoDraft,
    ValidationFailed,
    check_bet,
    distribution,
    validate_prono,
)
from sybille.domain.lifecycle import State

pytestmark = pytest.mark.unit

NOW = datetime(2026, 12, 3, 9, 0, tzinfo=UTC)
TODAY = date(2026, 12, 3)


def draft(**changes: object) -> PronoDraft:
    values: dict[str, object] = {
        "kind": Kind.CHOICE,
        "question": "Nice ou Monaco samedi ?",
        "options": ["Nice", "Nul", "Monaco"],
        "base_gain": 20,
        "closes_at": NOW + timedelta(days=3),
    }
    values.update(changes)
    return PronoDraft(**values)  # type: ignore[arg-type]


def fields_of(make: PronoDraft, max_base_gain: int = 50) -> dict[str, str]:
    with pytest.raises(ValidationFailed) as refused:
        validate_prono(make, max_base_gain=max_base_gain, now=NOW)
    return refused.value.fields


def test_a_valid_choice_prono_keeps_its_options() -> None:
    assert validate_prono(draft(), max_base_gain=50, now=NOW) == ["Nice", "Nul", "Monaco"]


def test_yes_no_gets_its_two_options() -> None:
    assert validate_prono(draft(kind=Kind.YES_NO, options=[]), max_base_gain=50, now=NOW) == [
        "Oui",
        "Non",
    ]


@pytest.mark.parametrize("kind", [Kind.NUMBER, Kind.DATE])
def test_number_and_date_have_no_options(kind: Kind) -> None:
    assert validate_prono(draft(kind=kind, options=[]), max_base_gain=50, now=NOW) == []
    assert "options" in fields_of(draft(kind=kind, options=["A", "B"]))


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"question": "Qui"}, "question"),
        ({"question": "x" * 201}, "question"),
        ({"link_url": "http://exemple.fr"}, "link_url"),
        ({"base_gain": -1}, "base_gain"),
        ({"base_gain": 51}, "base_gain"),
        ({"options": ["Seul"]}, "options"),
        ({"options": ["Nice", ""]}, "options"),
        ({"options": ["Nice", "x" * 81]}, "options"),
        ({"options": ["Nice", "nice"]}, "options"),
        ({"closes_at": None}, "closes_at"),
        ({"closes_at": NOW - timedelta(minutes=1)}, "closes_at"),
        ({"open_ended": True, "closes_at": None}, "open_ended"),
        (
            {"result_expected_at": NOW + timedelta(days=1)},
            "result_expected_at",
        ),
        ({"opens_at": NOW + timedelta(days=4)}, "opens_at"),
    ],
)
def test_invalid_pronos_are_refused(changes: dict[str, object], field: str) -> None:
    assert field in fields_of(draft(**changes))


def test_an_open_ended_date_has_no_closing() -> None:
    open_ended = draft(kind=Kind.DATE, options=[], open_ended=True, closes_at=None)
    assert validate_prono(open_ended, max_base_gain=50, now=NOW) == []
    with_closing = draft(kind=Kind.DATE, options=[], open_ended=True)
    assert "closes_at" in fields_of(with_closing)


def bet(**changes: object) -> None:
    values: dict[str, object] = {
        "state": State.OPEN,
        "kind": Kind.CHOICE,
        "open_ended": False,
        "closes_at": NOW + timedelta(hours=1),
        "now": NOW,
        "today": TODAY,
        "balance": 100,
        "stake": 20,
        "answer": Answer(option_id="opt"),
        "active_bet_date": None,
        "has_active_bet": False,
    }
    values.update(changes)
    check_bet(**values)  # type: ignore[arg-type]


def refusal(**changes: object) -> str:
    with pytest.raises(BetRefused) as refused:
        bet(**changes)
    return refused.value.code


def test_a_normal_bet_passes() -> None:
    bet()
    bet(stake=0)
    bet(stake=100)


@pytest.mark.parametrize("state", [s for s in State if s is not State.OPEN])
def test_bets_only_while_open(state: State) -> None:
    assert refusal(state=state) == "invalid_state"


def test_no_bet_from_the_closing_instant() -> None:
    assert refusal(closes_at=NOW) == "invalid_state"


def test_stakes_are_bounded_by_the_balance() -> None:
    assert refusal(stake=101) == "insufficient_balance"
    assert refusal(stake=-1) == "validation_error"
    assert refusal(balance=-10, stake=5) == "insufficient_balance"
    bet(balance=-10, stake=0)


def test_one_active_bet_per_prono() -> None:
    assert refusal(has_active_bet=True) == "already_bet"


def test_an_open_ended_date_can_be_bet_again_once_its_day_has_passed() -> None:
    open_ended = {
        "kind": Kind.DATE,
        "open_ended": True,
        "closes_at": None,
        "answer": Answer(date_value=TODAY + timedelta(days=5)),
    }
    bet(**open_ended)
    assert refusal(**open_ended, has_active_bet=True, active_bet_date=TODAY) == "already_bet"
    bet(**open_ended, has_active_bet=True, active_bet_date=TODAY - timedelta(days=1))
    assert refusal(**{**open_ended, "answer": Answer(date_value=TODAY)}) == "validation_error"


@pytest.mark.parametrize(
    ("kind", "answer"),
    [
        (Kind.CHOICE, Answer(number_value=Decimal(3))),
        (Kind.YES_NO, Answer()),
        (Kind.NUMBER, Answer(option_id="opt")),
        (Kind.NUMBER, Answer(number_value=Decimal("1.234"))),
        (Kind.DATE, Answer(number_value=Decimal(3))),
    ],
)
def test_the_answer_must_fit_the_kind(kind: Kind, answer: Answer) -> None:
    assert refusal(kind=kind, answer=answer) == "validation_error"


def test_distribution_keeps_few_values_and_buckets_many() -> None:
    few = distribution([(Decimal(1), 10), (Decimal(1), 0), (Decimal(3), 5)])
    assert [(b.label, b.count, b.stake_total) for b in few] == [("1", 2, 10), ("3", 1, 5)]
    many = distribution([(Decimal(v), 1) for v in range(0, 100)], buckets=4)
    assert len(many) == 4
    assert sum(b.count for b in many) == 100
    days = distribution([(date(2026, 12, d), 2) for d in (5, 5, 6)])
    assert [(b.label, b.count) for b in days] == [("2026-12-05", 2), ("2026-12-06", 1)]
