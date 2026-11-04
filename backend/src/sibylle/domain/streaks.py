"""The chain of wins (« chaîne de victoires », research.md J8): the pronos a member won in a row
up to the latest result, and the longest such chain, their record."""

from collections.abc import Iterable
from dataclasses import dataclass

# A single win is not a chain yet: the flame shows from two wins in a row.
SHOWN_FROM = 2


@dataclass(frozen=True)
class Streak:
    current: int
    best: int

    @property
    def shown(self) -> bool:
        return self.current >= SHOWN_FROM


def streak(wins: Iterable[bool]) -> Streak:
    """`wins`: the member's settled bets, oldest first in the order their pronos were first
    settled, True for a win and False for a loss; a refund is neither and stays out."""
    current = best = 0
    for won in wins:
        current = current + 1 if won else 0
        best = max(best, current)
    return Streak(current, best)
