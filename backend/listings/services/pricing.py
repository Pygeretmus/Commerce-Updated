from decimal import Decimal

# (the price is below this limit, the next bid must be at least this much higher), checked from the top
INCREMENT_TIERS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal(1), Decimal('0.05')),
    (Decimal(5), Decimal('0.25')),
    (Decimal(25), Decimal('0.50')),
    (Decimal(100), Decimal('1.00')),
    (Decimal(250), Decimal('2.50')),
    (Decimal(500), Decimal('5.00')),
    (Decimal(1000), Decimal('10.00')),
    (Decimal(2500), Decimal('25.00')),
    (Decimal(5000), Decimal('50.00')),
)
TOP_INCREMENT = Decimal('100.00')


def bid_increment(price: Decimal) -> Decimal:
    """The smallest raise allowed over the current price."""
    for limit, increment in INCREMENT_TIERS:
        if price < limit:
            return increment
    return TOP_INCREMENT


def next_min_bid(starting_price: Decimal, current_price: Decimal, bids_count: int) -> Decimal:
    """The first bid may equal the starting price, every next one must beat the current price by the increment."""
    if bids_count == 0:
        return starting_price
    return current_price + bid_increment(current_price)
