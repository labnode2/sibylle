import pytest

from sybille.domain import ledger
from sybille.domain.ledger import Effect, LedgerKind

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("effect", "expected"),
    [
        (ledger.starting_balance(100), Effect(LedgerKind.STARTING_BALANCE, 100, 0)),
        (ledger.stake(20), Effect(LedgerKind.STAKE, -20, 0)),
        (ledger.stake(0), Effect(LedgerKind.STAKE, 0, 0)),
        (ledger.base_gain(20), Effect(LedgerKind.BASE_GAIN, 20, 20)),
        (ledger.early_bird(4), Effect(LedgerKind.EARLY_BIRD, 4, 4)),
        (ledger.pot_share(40, stake=10), Effect(LedgerKind.POT_SHARE, 40, 30)),
        (ledger.stake_lost(10), Effect(LedgerKind.STAKE_LOST, 0, -10)),
        (ledger.refund(10), Effect(LedgerKind.REFUND, 10, 0)),
        (ledger.purchase(40), Effect(LedgerKind.PURCHASE, -40, 0)),
        (ledger.minigame(10), Effect(LedgerKind.MINIGAME, 10, 0)),
        (ledger.adjustment(-15), Effect(LedgerKind.ADJUSTMENT, -15, 0)),
        (ledger.adjustment(5), Effect(LedgerKind.ADJUSTMENT, 5, 0)),
        (ledger.season_reset(starting=100, current=342), Effect(LedgerKind.SEASON_RESET, -242, 0)),
        (ledger.season_reset(starting=100, current=-10), Effect(LedgerKind.SEASON_RESET, 110, 0)),
    ],
)
def test_effects_on_balance_and_score(effect: Effect, expected: Effect) -> None:
    assert effect == expected


def test_reversal_undoes_an_entry_exactly() -> None:
    share = ledger.pot_share(40, stake=10)
    reversal = ledger.reversal(share)
    assert reversal == Effect(LedgerKind.REVERSAL, -40, -30)
    assert share.amount + reversal.amount == 0
    assert share.score_delta + reversal.score_delta == 0


def test_a_purchase_never_changes_the_score() -> None:
    assert ledger.purchase(80).score_delta == 0


@pytest.mark.parametrize(
    "make",
    [
        lambda: ledger.starting_balance(-1),
        lambda: ledger.stake(-1),
        lambda: ledger.base_gain(-1),
        lambda: ledger.early_bird(-1),
        lambda: ledger.pot_share(-1, stake=0),
        lambda: ledger.pot_share(5, stake=-1),
        lambda: ledger.stake_lost(-1),
        lambda: ledger.refund(-1),
        lambda: ledger.purchase(0),
        lambda: ledger.minigame(0),
        lambda: ledger.adjustment(0),
    ],
)
def test_invalid_amounts_are_refused(make: object) -> None:
    with pytest.raises(ValueError):
        make()  # type: ignore[operator]
