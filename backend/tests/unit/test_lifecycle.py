from datetime import UTC, datetime, timedelta

import pytest

from sibylle.domain.lifecycle import (
    Event,
    InvalidTransition,
    State,
    can_delete,
    can_edit,
    closing_now,
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
    (S.RESOLVED, E.UNRESOLVE, {"bet_count": 1}, S.CLOSED),
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


def test_a_cancelled_result_waits_again_for_one() -> None:
    """Back to closed; an open-ended date opens again, as when it was resolved."""
    assert transition(S.RESOLVED, E.UNRESOLVE, bet_count=2) == S.CLOSED
    assert transition(S.RESOLVED, E.UNRESOLVE, open_ended=True, bet_count=2) == S.OPEN
    assert transition(S.OPEN, E.RESOLVE, open_ended=True, bet_count=2) == S.RESOLVED
    for state in (S.OPEN, S.CLOSED, S.CANCELLED):
        with pytest.raises(InvalidTransition):
            transition(state, E.UNRESOLVE, open_ended=True, bet_count=2)


def test_the_newsroom_may_close_an_open_prono_early() -> None:
    """« Clore les paris maintenant »: the same closing as the worker's, with or without bets;
    never for an open-ended date, which has no closing, nor from any other state."""
    for bet_count in (0, 3):
        assert transition(S.OPEN, E.CLOSE, bet_count=bet_count) == S.CLOSED
    with pytest.raises(InvalidTransition):
        transition(S.OPEN, E.CLOSE, open_ended=True, bet_count=3)
    for state in set(State) - {S.OPEN}:
        with pytest.raises(InvalidTransition):
            transition(state, E.CLOSE, bet_count=3)


def test_closing_early_takes_the_moment_of_the_closure() -> None:
    """The planned closing moves back to now; one already passed, which the worker has not
    reached yet, stays: the bets stopped then."""
    now = datetime(2026, 11, 19, 21, 0, tzinfo=UTC)
    planned = now + timedelta(days=2)
    assert closing_now(planned, now) == now
    assert closing_now(now - timedelta(seconds=30), now) == now - timedelta(seconds=30)
    assert closing_now(now, now) == now
    assert closing_now(None, now) == now


def test_a_prono_closed_early_is_resolved_at_once() -> None:
    """Nothing waits for the expected result: a closed prono with bets is resolved whenever
    the result is known."""
    closed = transition(S.OPEN, E.CLOSE, bet_count=2)
    assert transition(closed, E.RESOLVE, bet_count=2) == S.RESOLVED


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
        # After the first bet, in part (betting.locked_fields), until the result.
        (S.OPEN, 1, True),
        (S.CLOSED, 3, True),
        # Closed without bets: relaunched or cancelled, as before.
        (S.CLOSED, 0, False),
        (S.RESOLVED, 2, False),
        (S.REJECTED, 0, False),
        (S.CANCELLED, 0, False),
        (S.CANCELLED, 2, False),
    ],
)
def test_editing_lasts_until_the_result(state: State, bet_count: int, expected: bool) -> None:
    assert can_edit(state, bet_count) is expected


@pytest.mark.parametrize("state", list(State))
def test_only_a_cancelled_prono_can_be_deleted(state: State) -> None:
    """Deleting tidies the lists: only a cancelled prono, whose stakes are all back."""
    assert can_delete(state) is (state is S.CANCELLED)
    assert can_delete(state.value) is (state is S.CANCELLED)
