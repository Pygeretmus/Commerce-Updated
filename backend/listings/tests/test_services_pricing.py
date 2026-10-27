from decimal import Decimal

from django.test import SimpleTestCase

from ..services.pricing import bid_increment, next_min_bid


class BidIncrementTest(SimpleTestCase):
    def test_it_follows_the_increment_table(self):
        # (current price, expected increment), including both sides of every boundary
        cases = [
            ('0.01', '0.05'),
            ('0.99', '0.05'),
            ('1.00', '0.25'),
            ('4.99', '0.25'),
            ('5.00', '0.50'),
            ('24.99', '0.50'),
            ('25.00', '1.00'),
            ('99.99', '1.00'),
            ('100.00', '2.50'),
            ('249.99', '2.50'),
            ('250.00', '5.00'),
            ('499.99', '5.00'),
            ('500.00', '10.00'),
            ('999.99', '10.00'),
            ('1000.00', '25.00'),
            ('2499.99', '25.00'),
            ('2500.00', '50.00'),
            ('4999.99', '50.00'),
            ('5000.00', '100.00'),
            ('9999999999.99', '100.00'),
        ]
        for price, expected in cases:
            with self.subTest(price=price):
                self.assertEqual(bid_increment(Decimal(price)), Decimal(expected))


class NextMinBidTest(SimpleTestCase):
    def test_it_allows_the_first_bid_to_equal_the_starting_price(self):
        self.assertEqual(next_min_bid(Decimal('10.00'), Decimal('10.00'), 0), Decimal('10.00'))

    def test_it_adds_the_increment_to_the_current_price_after_the_first_bid(self):
        self.assertEqual(next_min_bid(Decimal('10.00'), Decimal('10.00'), 1), Decimal('10.50'))
        self.assertEqual(next_min_bid(Decimal('10.00'), Decimal('99.50'), 3), Decimal('100.50'))
        self.assertEqual(next_min_bid(Decimal('10.00'), Decimal('100.00'), 4), Decimal('102.50'))
