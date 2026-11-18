from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import get_args

import pytest

from sibylle.api.schemas import LockedField
from sibylle.domain.betting import (
    LOCKED_AFTER_BETS,
    Answer,
    BetRefused,
    Kind,
    PronoDraft,
    ValidationFailed,
    check_bet,
    distribution,
    locked_fields,
    validate_prono,
)
from sibylle.domain.lifecycle import State

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


def test_nothing_is_locked_before_the_first_bet() -> None:
    assert locked_fields(State.OPEN, 0) == ()
    assert locked_fields(State.SCHEDULED, 0) == ()
    assert set(locked_fields(State.OPEN, 1)) == {
        "kind",
        "options",
        "open_ended",
        "base_gain",
        "number_unit",
        "opens_at",
    }
    # Closed bets reopen with a relaunch, not an edit.
    assert set(locked_fields(State.CLOSED, 1)) == {*LOCKED_AFTER_BETS, "closes_at"}
    # The API names every one of them.
    assert set(get_args(LockedField)) == {*LOCKED_AFTER_BETS, "closes_at"}


def edited(changes: dict[str, object], state: State = State.OPEN, **current: object) -> list[str]:
    """Validates an edit of a prono someone bet on: `current` as it stands, `changes` asked."""
    placed = draft(**current)
    values = {**placed.__dict__, **changes}
    return validate_prono(
        PronoDraft(**values),  # type: ignore[arg-type]
        max_base_gain=50,
        now=NOW,
        current=placed,
        locked=locked_fields(state, 3),
    )


def edit_refused(
    changes: dict[str, object], state: State = State.OPEN, **current: object
) -> dict[str, str]:
    with pytest.raises(ValidationFailed) as refused:
        edited(changes, state, **current)
    return refused.value.fields


def test_after_bets_the_wording_and_the_dates_can_change() -> None:
    assert edited(
        {
            "question": "Nice ou Monaco dimanche ?",
            "link_url": "https://exemple.fr/match",
            "closes_at": NOW + timedelta(days=5),
            "result_expected_at": NOW + timedelta(days=6),
        }
    ) == ["Nice", "Nul", "Monaco"]
    # The same answers, spaces aside, are no change.
    assert edited({"options": [" Nice", "Nul ", "Monaco"]}) == ["Nice", "Nul", "Monaco"]
    yes_no = {"kind": Kind.YES_NO, "options": ["Oui", "Non"]}
    assert edited({"options": []}, **yes_no) == ["Oui", "Non"]


@pytest.mark.parametrize(
    ("changes", "current"),
    [
        ({"kind": Kind.YES_NO, "options": []}, {}),
        ({"options": ["Nice", "Monaco"]}, {}),
        ({"options": ["Nice", "Nul", "Monaco", "Lyon"]}, {}),
        ({"base_gain": 30}, {}),
        (
            {"open_ended": False, "closes_at": NOW + timedelta(days=3)},
            {"kind": Kind.DATE, "options": [], "open_ended": True, "closes_at": None},
        ),
        ({"number_unit": "€"}, {"kind": Kind.NUMBER, "options": [], "number_unit": "%"}),
        ({"opens_at": NOW + timedelta(days=1)}, {}),
    ],
)
def test_after_bets_what_was_bet_on_is_locked(
    changes: dict[str, object], current: dict[str, object]
) -> None:
    fields = edit_refused(changes, **current)
    for name in changes.keys() & set(LOCKED_AFTER_BETS):
        assert fields[name] == "locked_after_bets"


def test_after_bets_the_closing_only_moves_later() -> None:
    assert edit_refused({"closes_at": NOW + timedelta(days=2)}) == {"closes_at": "not_later"}
    assert edit_refused({"closes_at": NOW - timedelta(days=1)}) == {"closes_at": "not_later"}
    # An open prono past its closing, not yet closed by the worker: still not into the past.
    late = {"closes_at": NOW - timedelta(hours=2)}
    assert edit_refused({"closes_at": NOW - timedelta(hours=1)}, **late) == {"closes_at": "past"}
    assert edited({"closes_at": NOW + timedelta(hours=1)}, **late)


def test_a_closed_prono_keeps_its_past_closing() -> None:
    past = {"closes_at": NOW - timedelta(days=1)}
    assert edited({"question": "Nice ou Monaco dimanche ?"}, State.CLOSED, **past)
    # The result expected later than announced, the closing kept as it is.
    assert edited({"result_expected_at": NOW + timedelta(days=2)}, State.CLOSED, **past)
    later = {"closes_at": NOW + timedelta(days=3)}
    assert edit_refused(later, State.CLOSED, **past) == {"closes_at": "locked_after_bets"}


def test_a_kept_gain_stays_above_a_lowered_ceiling() -> None:
    assert edited({"question": "Nice ou Monaco dimanche ?"}, base_gain=80)
    assert edit_refused({"base_gain": 40}, base_gain=80) == {"base_gain": "locked_after_bets"}


def test_without_bets_the_closing_moves_freely() -> None:
    sooner = draft(closes_at=NOW + timedelta(days=1))
    assert validate_prono(sooner, max_base_gain=50, now=NOW, current=draft())


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


@pytest.mark.parametrize("open_ended", [True, False])
def test_a_date_bet_must_be_strictly_after_today(open_ended: bool) -> None:
    base = {"kind": Kind.DATE, "open_ended": open_ended}
    if open_ended:
        base["closes_at"] = None
    for past in (TODAY, TODAY - timedelta(days=3)):
        assert refusal(**base, answer=Answer(date_value=past)) == "validation_error"
    bet(**base, answer=Answer(date_value=TODAY + timedelta(days=1)))


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
