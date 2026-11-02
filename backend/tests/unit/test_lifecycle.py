import pytest

from sibylle.domain.lifecycle import (
    Event,
    InvalidTransition,
    State,
    can_edit,
    transition,
)

pytestmark = pytest.mark.unit

S, E = State, Event

ALLOWED = [
    (S.PROPOSED, E.VALIDATE, {}, S.OPEN),
    (S.PROPOSED, E.VALIDATE, {"opens_in_future": True}, S.SCHEDULED),
    (S.PROPOSED, E.REJECT, {}, S.REJECTED),
    (S.SCHEDULED, E.OPEN, {}, S.OPEN),
    (S.OPEN, E.CLOSE, {}, S.CLOSED),
    (S.OPEN, E.RESOLVE, {"open_ended": True, "bet_count": 3}, S.RESOLVED),
    (S.CLOSED, E.RESOLVE, {"bet_count": 1}, S.RESOLVED),
    (S.CLOSED, E.RELAUNCH, {}, S.OPEN),
    (S.RESOLVED, E.CORRECT, {"bet_count": 1}, S.RESOLVED),
    (S.SCHEDULED, E.CANCEL, {}, S.CANCELLED),
    (S.OPEN, E.CANCEL, {}, S.CANCELLED),
    (S.CLOSED, E.CANCEL, {}, S.CANCELLED),
    (S.RESOLVED, E.CANCEL, {}, S.CANCELLED),
]


@pytest.mark.parametrize(("state", "event", "context", "expected"), ALLOWED)
def test_allowed_transitions(
    state: State, event: Event, context: dict[str, object], expected: State
) -> None:
    assert transition(state, event, **context) == expected  # type: ignore[arg-type]


def test_every_other_transition_is_refused() -> None:
    allowed = {(state, event) for state, event, _, _ in ALLOWED}
    for state in State:
        for event in Event:
            if (state, event) in allowed:
                continue
            with pytest.raises(InvalidTransition):
                transition(state, event, bet_count=5, open_ended=False)


def test_an_open_prono_only_resolves_directly_when_open_ended() -> None:
    with pytest.raises(InvalidTransition):
        transition(S.OPEN, E.RESOLVE, bet_count=3)
    with pytest.raises(InvalidTransition):
        transition(S.OPEN, E.CLOSE, open_ended=True)


def test_a_prono_without_bets_is_not_resolved() -> None:
    with pytest.raises(InvalidTransition):
        transition(S.CLOSED, E.RESOLVE, bet_count=0)
    assert transition(S.CLOSED, E.RELAUNCH, bet_count=0) == S.OPEN
    assert transition(S.CLOSED, E.CANCEL, bet_count=0) == S.CANCELLED


@pytest.mark.parametrize(
    ("state", "bet_count", "expected"),
    [
        (S.PROPOSED, 0, True),
        (S.SCHEDULED, 0, True),
        (S.OPEN, 0, True),
        (S.OPEN, 1, False),
        (S.CLOSED, 0, False),
        (S.RESOLVED, 0, False),
        (S.REJECTED, 0, False),
        (S.CANCELLED, 0, False),
    ],
)
def test_editing_stops_at_the_first_bet(state: State, bet_count: int, expected: bool) -> None:
    assert can_edit(state, bet_count) is expected
