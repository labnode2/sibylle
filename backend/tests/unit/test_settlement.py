import uuid
from collections import defaultdict

import pytest

from sibylle.domain.ledger import Effect, LedgerKind
from sibylle.domain.settlement import (
    BetLine,
    Outcome,
    refunds,
    settle,
    winners_by_options,
)

pytestmark = pytest.mark.unit

YES, NO, DRAW = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def bet(rank: int, stake: int, option: uuid.UUID | None = YES, *, active: bool = True) -> BetLine:
    return BetLine(
        id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        stake=stake,
        rank=rank,
        active=active,
        option_id=option,
    )


def totals(outcome: Outcome) -> dict[uuid.UUID, tuple[int, int]]:
    """(balance, score) moved by the settlement, per member."""
    moved: dict[uuid.UUID, list[int]] = defaultdict(lambda: [0, 0])
    for entry in outcome.entries:
        moved[entry.member_id][0] += entry.effect.amount
        moved[entry.member_id][1] += entry.effect.score_delta
    return {member: (balance, score) for member, (balance, score) in moved.items()}


def payout_of(outcome: Outcome, line: BetLine) -> int:
    return next((p.total for p in outcome.payouts if p.bet_id == line.id), 0)


def no_bonus(bets: list[BetLine], winners: frozenset[uuid.UUID], gain: int = 20) -> Outcome:
    return settle(bets, winners, base_gain=gain, early_bird_pct=0, early_bird_count=0)


# Winners of a choice or yes/no prono


def test_winners_are_the_bets_on_a_correct_answer() -> None:
    a, b, c = bet(1, 10, YES), bet(2, 10, NO), bet(3, 10, DRAW)
    assert winners_by_options([a, b, c], {YES}) == {a.id}


def test_several_answers_can_be_correct() -> None:
    a, b, c = bet(1, 10, YES), bet(2, 10, NO), bet(3, 10, DRAW)
    assert winners_by_options([a, b, c], {YES, DRAW}) == {a.id, c.id}


def test_a_replaced_bet_never_wins() -> None:
    old = bet(1, 10, YES, active=False)
    assert winners_by_options([old], {YES}) == frozenset()
    with pytest.raises(ValueError):
        no_bonus([old], frozenset({old.id}))


# The spec's examples


def test_four_stakes_of_ten_and_one_winner() -> None:
    winner = bet(1, 10, YES)
    losers = [bet(rank, 10, NO) for rank in (2, 3, 4)]
    outcome = no_bonus([winner, *losers], frozenset({winner.id}))

    [payout] = outcome.payouts
    assert (payout.base_gain, payout.early_bird, payout.pot_share) == (20, 0, 40)
    moved = totals(outcome)
    # The stake left the balance when the bet was placed: +20 +40 now, score +20 +30.
    assert moved[winner.member_id] == (60, 50)
    for loser in losers:
        assert moved[loser.member_id] == (0, -10)
    assert sum(p.pot_share for p in outcome.payouts) == outcome.pot == 40
    assert not outcome.pot_lost


def test_stakes_of_thirty_and_ten_share_a_pot_of_a_hundred() -> None:
    big, small = bet(1, 30), bet(2, 10)
    losers = [bet(3, 40, NO), bet(4, 20, NO)]
    outcome = no_bonus([big, small, *losers], frozenset({big.id, small.id}))

    shares = {p.bet_id: p.pot_share for p in outcome.payouts}
    assert shares == {big.id: 75, small.id: 25}
    assert payout_of(outcome, big) == 20 + 75


def test_early_bird_bonus_of_twenty_percent_on_twenty() -> None:
    first, third, sixth = bet(1, 0), bet(3, 0), bet(6, 0)
    outcome = settle(
        [first, third, sixth],
        frozenset({first.id, third.id, sixth.id}),
        base_gain=20,
        early_bird_pct=20,
        early_bird_count=5,
    )
    bonus = {p.bet_id: p.early_bird for p in outcome.payouts}
    assert bonus == {first.id: 4, third.id: 4, sixth.id: 0}


def test_early_bird_is_rounded_down() -> None:
    fifth = bet(5, 0)
    outcome = settle(
        [fifth], frozenset({fifth.id}), base_gain=15, early_bird_pct=20, early_bird_count=5
    )
    assert outcome.payouts[0].early_bird == 3


# The pot


def test_the_pot_counts_replaced_stakes() -> None:
    old = bet(1, 30, NO, active=False)
    new = BetLine(id=uuid.uuid4(), member_id=old.member_id, stake=10, rank=3, option_id=YES)
    other = bet(2, 20, NO)
    outcome = no_bonus([old, new, other], frozenset({new.id}))

    assert outcome.pot == 60
    assert outcome.payouts[0].pot_share == 60
    # The replaced stake is lost: it counts against the score once.
    assert totals(outcome)[old.member_id] == (20 + 60, 20 + 50 - 30)


def test_the_remainder_goes_one_laurel_at_a_time_by_stake_then_rank() -> None:
    # P = 100, S_W = 30: floor(100 × 10 / 30) = 33 each, one laurel left.
    a, b, c = bet(3, 10), bet(1, 10), bet(2, 10)
    loser = bet(4, 70, NO)
    outcome = no_bonus([a, b, c, loser], frozenset({a.id, b.id, c.id}))
    shares = {p.bet_id: p.pot_share for p in outcome.payouts}
    assert shares == {b.id: 34, c.id: 33, a.id: 33}


def test_the_largest_stake_gets_the_remainder_first() -> None:
    # P = 101, S_W = 30: 67.33 and 33.67 → 67 and 33, one laurel left.
    big, small = bet(2, 20), bet(1, 10)
    loser = bet(3, 71, NO)
    outcome = no_bonus([big, small, loser], frozenset({big.id, small.id}))
    shares = {p.bet_id: p.pot_share for p in outcome.payouts}
    assert shares == {big.id: 68, small.id: 33}
    assert sum(shares.values()) == 101


def test_the_pot_is_lost_without_winners() -> None:
    a, b = bet(1, 10, NO), bet(2, 20, NO)
    outcome = no_bonus([a, b], frozenset())
    assert outcome.pot_lost
    assert outcome.payouts == ()
    assert totals(outcome) == {a.member_id: (0, -10), b.member_id: (0, -20)}


def test_the_pot_is_lost_when_winners_staked_nothing() -> None:
    winner, loser = bet(1, 0), bet(2, 25, NO)
    outcome = no_bonus([winner, loser], frozenset({winner.id}))
    assert outcome.pot_lost
    assert outcome.payouts[0].pot_share == 0
    assert payout_of(outcome, winner) == 20
    assert totals(outcome)[loser.member_id] == (0, -25)


def test_an_empty_pot_is_not_lost() -> None:
    winner = bet(1, 0)
    assert not no_bonus([winner], frozenset({winner.id})).pot_lost


# Ledger entries


def test_entries_written_for_each_bet() -> None:
    winner = bet(1, 10)
    loser = bet(2, 10, NO)
    replaced = bet(3, 5, NO, active=False)
    free_loser = bet(4, 0, NO)
    outcome = settle(
        [winner, loser, replaced, free_loser],
        frozenset({winner.id}),
        base_gain=20,
        early_bird_pct=20,
        early_bird_count=1,
    )
    kinds = [(e.bet_id, e.effect) for e in outcome.entries]
    assert kinds == [
        (winner.id, Effect(LedgerKind.BASE_GAIN, 20, 20)),
        (winner.id, Effect(LedgerKind.EARLY_BIRD, 4, 4)),
        (winner.id, Effect(LedgerKind.POT_SHARE, 25, 15)),
        (loser.id, Effect(LedgerKind.STAKE_LOST, 0, -10)),
        (replaced.id, Effect(LedgerKind.STAKE_LOST, 0, -5)),
    ]
    assert outcome.losers == (loser.id, replaced.id, free_loser.id)


def test_no_entry_for_a_zero_base_gain() -> None:
    winner = bet(1, 0)
    assert no_bonus([winner], frozenset({winner.id}), gain=0).entries == ()


def test_refunds_give_every_stake_back() -> None:
    a, b, replaced, free = bet(1, 10), bet(2, 30, NO), bet(3, 5, active=False), bet(4, 0)
    entries = refunds([a, b, replaced, free])
    assert [(e.bet_id, e.effect) for e in entries] == [
        (a.id, Effect(LedgerKind.REFUND, 10, 0)),
        (b.id, Effect(LedgerKind.REFUND, 30, 0)),
        (replaced.id, Effect(LedgerKind.REFUND, 5, 0)),
    ]
