from sibylle.domain.coins import gold, weekly_amount


def test_gold_laurels_are_the_balance_plus_the_stakes_in_play() -> None:
    assert gold(90, 30) == 120
    assert gold(-15, 0) == -15


def test_monday_gives_one_coin_per_gold_laurel() -> None:
    assert weekly_amount(120) == 120
    assert weekly_amount(0) == 0


def test_no_coins_for_gold_laurels_below_zero() -> None:
    assert weekly_amount(-15) == 0
