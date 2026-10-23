from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django_dynamic_fixture import G

from ..models import Bid
from .helpers import make_active_listing

User = get_user_model()


class BidConstraintsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bidder = G(User)
        cls.listing = make_active_listing(seller=G(User), starting_price=Decimal('10.00'))

    def make_bid(self, amount, listing=None, bidder=None) -> Bid:
        return Bid.objects.create(listing=listing or self.listing, bidder=bidder or self.bidder, amount=Decimal(amount))

    def test_it_rejects_zero_and_negative_amounts(self):
        for amount in ('0', '-1'):
            with (
                self.subTest(amount=amount),
                self.assertRaisesMessage(IntegrityError, 'bid_amount_positive'),
                transaction.atomic(),
            ):
                self.make_bid(amount)

    def test_it_rejects_two_equal_bids_on_one_listing(self):
        # === Arrange ===
        self.make_bid('10.00')

        # === Act & Assert === (the lock in place_bid is the first defence, this is the last one)
        # (PostgreSQL names the constraint, SQLite names the columns)
        constraint = 'bid_unique_amount_per_listing|listings_bid.amount'
        with self.assertRaisesRegex(IntegrityError, constraint), transaction.atomic():
            self.make_bid('10.00', bidder=G(User))

    def test_it_allows_the_same_amount_on_different_listings(self):
        # === Arrange ===
        other = make_active_listing(seller=G(User), starting_price=Decimal('10.00'))
        self.make_bid('10.00')

        # === Act ===
        bid = self.make_bid('10.00', listing=other)

        # === Assert ===
        self.assertEqual(bid.amount, Decimal('10.00'))

    def test_it_keeps_the_bid_when_the_bidder_deletes_the_account(self):
        # === Arrange ===
        bid = self.make_bid('10.00', bidder=(bidder := G(User)))

        # === Act ===
        bidder.delete()

        # === Assert ===
        bid.refresh_from_db()
        self.assertIsNone(bid.bidder)

    def test_it_deletes_bids_with_the_listing(self):
        # === Arrange ===
        self.make_bid('10.00')

        # === Act ===
        self.listing.delete()

        # === Assert ===
        self.assertEqual(Bid.objects.count(), 0)

    def test_it_orders_bids_from_the_highest(self):
        # === Arrange ===
        for amount in ('10.00', '30.00', '20.00'):
            self.make_bid(amount, bidder=G(User))

        # === Act ===
        amounts = list(self.listing.bids.values_list('amount', flat=True))

        # === Assert ===
        self.assertEqual(amounts, [Decimal('30.00'), Decimal('20.00'), Decimal('10.00')])
