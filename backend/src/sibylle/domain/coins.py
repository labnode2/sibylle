"""Coins (research.md J6): laurels are for staking and ranking, coins for buying in the collection.

Every Monday at 00:00 (Paris), a member's gold laurels become as many coins, and the laurels stay.
Gold laurels are the balance plus the stakes still in play, the green laurels being the balance.
"""

from enum import StrEnum


class CoinKind(StrEnum):
    WEEKLY = "weekly"
    PURCHASE = "purchase"


def gold(balance: int, in_play: int) -> int:
    """Gold laurels: what the member can stake, plus what they staked on pronos not settled yet."""
    return balance + in_play


def weekly_amount(gold: int) -> int:
    """The coins of Monday's conversion: one per gold laurel, none below zero."""
    return max(gold, 0)
