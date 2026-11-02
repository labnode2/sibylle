"""The laurels ledger: every movement of laurels is one entry, never changed afterwards.

Each entry moves two counters of a member: the balance (what they can stake or spend) and the
season score (what the ranking uses: gains from pronos minus lost stakes). Only pronos move the
score; purchases, mini-games and the editor's adjustments touch the balance only.
"""

from dataclasses import dataclass
from enum import StrEnum


class LedgerKind(StrEnum):
    STARTING_BALANCE = "starting_balance"
    STAKE = "stake"
    BASE_GAIN = "base_gain"
    EARLY_BIRD = "early_bird"
    POT_SHARE = "pot_share"
    STAKE_LOST = "stake_lost"
    REFUND = "refund"
    REVERSAL = "reversal"
    PURCHASE = "purchase"
    MINIGAME = "minigame"
    ADJUSTMENT = "adjustment"
    SEASON_RESET = "season_reset"


@dataclass(frozen=True)
class Effect:
    kind: LedgerKind
    amount: int  # effect on the balance
    score_delta: int  # effect on the season score


def _at_least(value: int, minimum: int, what: str) -> int:
    if value < minimum:
        raise ValueError(f"{what} must be at least {minimum}, got {value}")
    return value


def starting_balance(amount: int) -> Effect:
    return Effect(LedgerKind.STARTING_BALANCE, _at_least(amount, 0, "starting balance"), 0)


def stake(stake: int) -> Effect:
    """Taken from the balance when the bet is placed; the score waits for the result."""
    return Effect(LedgerKind.STAKE, -_at_least(stake, 0, "stake"), 0)


def base_gain(gain: int) -> Effect:
    _at_least(gain, 0, "base gain")
    return Effect(LedgerKind.BASE_GAIN, gain, gain)


def early_bird(bonus: int) -> Effect:
    _at_least(bonus, 0, "early-bird bonus")
    return Effect(LedgerKind.EARLY_BIRD, bonus, bonus)


def pot_share(share: int, *, stake: int) -> Effect:
    """A winner's share of the pot. Their own stake comes back inside it: only the profit scores."""
    _at_least(share, 0, "pot share")
    _at_least(stake, 0, "stake")
    return Effect(LedgerKind.POT_SHARE, share, share - stake)


def stake_lost(stake: int) -> Effect:
    """A losing (or replaced) stake: already gone from the balance, now taken from the score."""
    return Effect(LedgerKind.STAKE_LOST, 0, -_at_least(stake, 0, "stake"))


def refund(stake: int) -> Effect:
    return Effect(LedgerKind.REFUND, _at_least(stake, 0, "refund"), 0)


def reversal(original: Effect) -> Effect:
    return Effect(LedgerKind.REVERSAL, -original.amount, -original.score_delta)


def purchase(price: int) -> Effect:
    return Effect(LedgerKind.PURCHASE, -_at_least(price, 1, "price"), 0)


def minigame(gain: int) -> Effect:
    return Effect(LedgerKind.MINIGAME, _at_least(gain, 1, "mini-game gain"), 0)


def adjustment(amount: int) -> Effect:
    if amount == 0:
        raise ValueError("an adjustment cannot be zero")
    return Effect(LedgerKind.ADJUSTMENT, amount, 0)


def season_reset(*, starting: int, current: int) -> Effect:
    """Brings the balance back to the newsroom's starting balance at the end of a season."""
    return Effect(LedgerKind.SEASON_RESET, starting - current, 0)
