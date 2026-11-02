"""The life of a prono (data-model.md, « Transitions d'état d'un prono »).

proposed → scheduled | open (validation), proposed → rejected
scheduled → open (opens_at), open → closed (closes_at)
closed → resolved (designation), open → resolved for an open-ended date
closed → open (relaunch, bets kept), resolved → resolved (correction)
scheduled | open | closed | resolved → cancelled
"""

from enum import StrEnum


class State(StrEnum):
    PROPOSED = "proposed"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class Event(StrEnum):
    VALIDATE = "validate"
    REJECT = "reject"
    OPEN = "open"
    CLOSE = "close"
    RESOLVE = "resolve"
    RELAUNCH = "relaunch"
    CORRECT = "correct"
    CANCEL = "cancel"


class InvalidTransition(Exception):
    def __init__(self, state: State, event: Event) -> None:
        super().__init__(f"{event} is not possible from {state}")
        self.state = state
        self.event = event


_CANCELLABLE = {State.SCHEDULED, State.OPEN, State.CLOSED, State.RESOLVED}
EDITABLE = {State.PROPOSED, State.SCHEDULED, State.OPEN}


def transition(
    state: State,
    event: Event,
    *,
    open_ended: bool = False,
    bet_count: int = 0,
    opens_in_future: bool = False,
) -> State:
    """The state after the event, or InvalidTransition."""
    state = State(state)
    match event:
        case Event.VALIDATE if state is State.PROPOSED:
            return State.SCHEDULED if opens_in_future else State.OPEN
        case Event.REJECT if state is State.PROPOSED:
            return State.REJECTED
        case Event.OPEN if state is State.SCHEDULED:
            return State.OPEN
        case Event.CLOSE if state is State.OPEN and not open_ended:
            return State.CLOSED
        # A prono nobody bet on is relaunched or cancelled, never resolved.
        case Event.RESOLVE if bet_count > 0 and (
            state is State.CLOSED or (state is State.OPEN and open_ended)
        ):
            return State.RESOLVED
        case Event.RELAUNCH if state is State.CLOSED:
            return State.OPEN
        case Event.CORRECT if state is State.RESOLVED:
            return State.RESOLVED
        case Event.CANCEL if state in _CANCELLABLE:
            return State.CANCELLED
    raise InvalidTransition(state, event)


def can_edit(state: State | str, bet_count: int) -> bool:
    """A prono can be edited until someone bets on it."""
    return bet_count == 0 and State(state) in EDITABLE
