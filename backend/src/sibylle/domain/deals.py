"""The deal of the week (research.md J10): one object of the collection, a share off its price."""

# The shares off a deal may take, drawn at random each week.
DISCOUNTS: tuple[int, ...] = (20, 30, 40, 50)


def deal_price(price: int, discount_pct: int) -> int:
    """The price once `discount_pct` % is off, rounded down to the coin, never free."""
    return max(1, price * (100 - discount_pct) // 100)
