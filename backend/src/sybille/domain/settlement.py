"""Settling a prono (research.md J1): who won, what each winner gets, which entries to write.

`G` is the prono's base gain, `P` its pot (every stake, replaced ones included), `W` the winning
bets, `s_i` a bet's stake and `S_W` the winning stakes. Each winner gets `G`, an early-bird bonus
`floor(G × p / 100)` when their rank is at most `N`, and `floor(P × s_i / S_W)` of the pot; the
laurels left by the rounding go one at a time to the winners by stake (largest first) then rank.
The pot is lost when nobody won or the winners staked nothing.
"""

import uuid
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sybille.domain import ledger
from sybille.domain.ledger import Effect


@dataclass(frozen=True)
class BetLine:
    """What the settlement needs to know about a bet."""

    id: uuid.UUID
    member_id: uuid.UUID
    stake: int
    rank: int
    # False for a replaced bet of an open-ended date prono: its stake is in the pot, it never wins.
    active: bool = True
    option_id: uuid.UUID | None = None
    value: Decimal | date | None = None


@dataclass(frozen=True)
class Payout:
    bet_id: uuid.UUID
    member_id: uuid.UUID
    stake: int
    base_gain: int
    early_bird: int
    pot_share: int

    @property
    def total(self) -> int:
        return self.base_gain + self.early_bird + self.pot_share


@dataclass(frozen=True)
class Entry:
    """A ledger entry to write."""

    member_id: uuid.UUID
    bet_id: uuid.UUID
    effect: Effect


@dataclass(frozen=True)
class Outcome:
    pot: int
    pot_lost: bool
    payouts: tuple[Payout, ...]  # one per winning bet, by rank
    losers: tuple[uuid.UUID, ...]  # losing and replaced bets, by rank
    entries: tuple[Entry, ...]

    @property
    def winners(self) -> frozenset[uuid.UUID]:
        return frozenset(p.bet_id for p in self.payouts)


def winners_by_options(
    bets: Iterable[BetLine], correct: Collection[uuid.UUID]
) -> frozenset[uuid.UUID]:
    """Choice and yes/no: the active bets whose answer is among the correct ones."""
    return frozenset(b.id for b in bets if b.active and b.option_id in correct)


def _pot_shares(winners: list[BetLine], pot: int) -> dict[uuid.UUID, int]:
    staked = sum(b.stake for b in winners)
    shares = {b.id: pot * b.stake // staked for b in winners}
    left = pot - sum(shares.values())
    order = sorted(winners, key=lambda b: (-b.stake, b.rank))
    while left:
        for line in order:
            if not left:
                break
            shares[line.id] += 1
            left -= 1
    return shares


def settle(
    bets: Sequence[BetLine],
    winners: Collection[uuid.UUID],
    *,
    base_gain: int,
    early_bird_pct: int,
    early_bird_count: int,
) -> Outcome:
    by_rank = sorted(bets, key=lambda b: b.rank)
    active = {b.id for b in by_rank if b.active}
    if not set(winners) <= active:
        raise ValueError("only active bets of the prono can win")
    won = [b for b in by_rank if b.id in winners]
    pot = sum(b.stake for b in by_rank)
    pot_lost = pot > 0 and sum(b.stake for b in won) == 0
    shares = {} if pot_lost or not pot else _pot_shares(won, pot)
    bonus = base_gain * early_bird_pct // 100

    payouts: list[Payout] = []
    losers: list[uuid.UUID] = []
    entries: list[Entry] = []
    for line in by_rank:
        if line.id not in winners:
            losers.append(line.id)
            if line.stake:
                entries.append(Entry(line.member_id, line.id, ledger.stake_lost(line.stake)))
            continue
        payout = Payout(
            bet_id=line.id,
            member_id=line.member_id,
            stake=line.stake,
            base_gain=base_gain,
            early_bird=bonus if line.rank <= early_bird_count else 0,
            pot_share=shares.get(line.id, 0),
        )
        payouts.append(payout)
        effects = [
            ledger.base_gain(payout.base_gain) if payout.base_gain else None,
            ledger.early_bird(payout.early_bird) if payout.early_bird else None,
            ledger.pot_share(payout.pot_share, stake=line.stake) if payout.pot_share else None,
        ]
        entries.extend(Entry(line.member_id, line.id, e) for e in effects if e is not None)
    return Outcome(
        pot=pot,
        pot_lost=pot_lost,
        payouts=tuple(payouts),
        losers=tuple(losers),
        entries=tuple(entries),
    )


def refunds(bets: Iterable[BetLine]) -> tuple[Entry, ...]:
    """A cancelled prono gives every stake back, replaced ones included."""
    return tuple(
        Entry(b.member_id, b.id, ledger.refund(b.stake))
        for b in sorted(bets, key=lambda b: b.rank)
        if b.stake
    )
