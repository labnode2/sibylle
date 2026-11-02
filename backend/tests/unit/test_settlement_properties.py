"""Properties of the settlement (research.md J1), checked on generated pronos."""

import random
import uuid
from collections import Counter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sybille.domain.ledger import LedgerKind, reversal
from sybille.domain.settlement import BetLine, Entry, Outcome, settle

pytestmark = pytest.mark.unit

Case = tuple[list[BetLine], frozenset[uuid.UUID], dict[str, int]]


@st.composite
def pronos(draw: st.DrawFn) -> Case:
    """Bets with gapless ranks, some replaced, a set of winners among the active ones."""
    count = draw(st.integers(min_value=1, max_value=12))
    ranks = draw(st.permutations(range(1, count + 1)))
    bets = [
        BetLine(
            id=uuid.UUID(int=i + 1),
            member_id=uuid.UUID(int=1000 + draw(st.integers(0, 5))),
            stake=draw(st.integers(min_value=0, max_value=500)),
            rank=rank,
            active=draw(st.booleans()) if i else True,
        )
        for i, rank in enumerate(ranks)
    ]
    active = sorted(b.id for b in bets if b.active)
    winners = frozenset(draw(st.lists(st.sampled_from(active), unique=True)))
    rules = {
        "base_gain": draw(st.integers(min_value=0, max_value=100)),
        "early_bird_pct": draw(st.integers(min_value=0, max_value=100)),
        "early_bird_count": draw(st.integers(min_value=0, max_value=10)),
    }
    return bets, winners, rules


def net(entries: list[Entry] | tuple[Entry, ...]) -> dict[tuple[uuid.UUID, str], int]:
    """Balance and score moved per member, without the members left unchanged."""
    moved: Counter[tuple[uuid.UUID, str]] = Counter()
    for entry in entries:
        moved[(entry.member_id, "balance")] += entry.effect.amount
        moved[(entry.member_id, "score")] += entry.effect.score_delta
    return {key: value for key, value in moved.items() if value}


def pot_shares(outcome: Outcome) -> int:
    return sum(e.effect.amount for e in outcome.entries if e.effect.kind is LedgerKind.POT_SHARE)


@given(pronos())
def test_the_pot_is_shared_exactly_or_lost(case: Case) -> None:
    bets, winners, rules = case
    outcome = settle(bets, winners, **rules)
    assert outcome.pot == sum(b.stake for b in bets)
    assert pot_shares(outcome) == (0 if outcome.pot_lost else outcome.pot)
    assert sum(p.pot_share for p in outcome.payouts) == pot_shares(outcome)


@given(pronos())
def test_no_share_or_gain_is_negative(case: Case) -> None:
    bets, winners, rules = case
    outcome = settle(bets, winners, **rules)
    for payout in outcome.payouts:
        assert payout.base_gain >= 0 and payout.early_bird >= 0 and payout.pot_share >= 0
        if not outcome.pot_lost:
            # A winner always gets at least their stake back.
            assert payout.pot_share >= payout.stake
    for entry in outcome.entries:
        if entry.effect.kind is not LedgerKind.STAKE_LOST:
            assert entry.effect.amount >= 0 and entry.effect.score_delta >= 0


@given(pronos())
def test_correcting_to_the_same_result_changes_nothing(case: Case) -> None:
    bets, winners, rules = case
    first = settle(bets, winners, **rules)
    correction = [Entry(e.member_id, e.bet_id, reversal(e.effect)) for e in first.entries] + list(
        settle(bets, winners, **rules).entries
    )
    assert net(list(first.entries) + correction) == net(first.entries)


@given(pronos(), st.randoms(use_true_random=False))
def test_the_order_of_the_bets_does_not_matter(case: Case, shuffler: random.Random) -> None:
    bets, winners, rules = case
    shuffled = list(bets)
    shuffler.shuffle(shuffled)
    assert settle(shuffled, winners, **rules) == settle(bets, winners, **rules)
