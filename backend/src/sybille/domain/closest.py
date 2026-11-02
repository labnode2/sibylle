"""Number and date pronos: the active bets closest to the real value win, ties included."""

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sybille.domain.settlement import BetLine


def _distance(value: Decimal | date, actual: Decimal | date) -> Decimal | int:
    if isinstance(value, date) and isinstance(actual, date):
        return abs((value - actual).days)
    if isinstance(value, Decimal) and isinstance(actual, Decimal):
        return abs(value - actual)
    raise TypeError(f"cannot compare {value!r} with {actual!r}")


def closest(bets: Iterable[BetLine], actual: Decimal | date) -> frozenset[uuid.UUID]:
    distances = {b.id: _distance(b.value, actual) for b in bets if b.active and b.value is not None}
    if not distances:
        return frozenset()
    best = min(distances.values())
    return frozenset(bet_id for bet_id, distance in distances.items() if distance == best)
