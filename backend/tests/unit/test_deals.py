import pytest

from sibylle.domain.deals import DISCOUNTS, deal_price

pytestmark = pytest.mark.unit


def test_the_discounts_on_offer() -> None:
    assert DISCOUNTS == (20, 30, 40, 50)


def test_the_price_comes_down_to_the_coin_below() -> None:
    assert deal_price(400, 30) == 280
    assert deal_price(600, 50) == 300
    assert deal_price(250, 30) == 175
    assert deal_price(5, 30) == 3  # 3.5 coins: 3


def test_a_deal_is_never_free() -> None:
    assert deal_price(1, 50) == 1
