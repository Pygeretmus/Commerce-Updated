from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_dynamic_fixture import G

from ..constants import SNIPING_WINDOW
from ..models import Bid, Listing
from ..services.bidding import BidRejected, place_bid
from .helpers import make_active_listing, make_listing

User = get_user_model()

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


class PlaceBidTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.alice = G(User)
        cls.bob = G(User)

    def setUp(self):
        self.listing = make_active_listing(
            seller=self.seller, starting_price=Decimal('10.00'), ends_at=NOW + timedelta(days=1)
        )

    def bid(self, bidder, amount, *, listing=None, now=NOW) -> Bid:
        return place_bid((listing or self.listing).pk, bidder, Decimal(amount), now=now)

    def assert_rejected(self, code, bidder, amount, *, listing=None, now=NOW):
        with self.assertRaises(BidRejected) as raised:
            self.bid(bidder, amount, listing=listing, now=now)
        self.assertEqual(raised.exception.get_codes(), code)
        return raised.exception

    def snapshot(self):
        row = Listing.objects.get(pk=self.listing.pk)
        return (row.current_price, row.bids_count, row.top_bid_id, row.ends_at, Bid.objects.count())

    # --- the first bid -------------------------------------------------------------------

    def test_it_accepts_first_bid_equal_to_starting_price(self):
        # === Act ===
        bid = self.bid(self.alice, '10.00')

        # === Assert ===
        self.assertEqual(bid.amount, Decimal('10.00'))
        self.assertEqual(bid.bidder, self.alice)
        self.assertEqual(bid.listing, self.listing)

    def test_it_accepts_first_bid_above_starting_price(self):
        # === Act ===
        self.bid(self.alice, '250.00')

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.current_price, Decimal('250.00'))

    def test_it_rejects_first_bid_below_starting_price(self):
        # === Act ===
        error = self.assert_rejected('bid_too_low', self.alice, '9.99')

        # === Assert ===
        self.assertEqual(error.min_bid, Decimal('10.00'))
        self.assertEqual(str(error.detail), 'Your bid is too low. The minimum is 10.00.')
        self.assertEqual(Bid.objects.count(), 0)

    # --- the next bids -------------------------------------------------------------------

    def test_it_updates_the_listing_after_a_bid(self):
        # === Act ===
        bid = self.bid(self.alice, '12.00')

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.current_price, Decimal('12.00'))
        self.assertEqual(self.listing.bids_count, 1)
        self.assertEqual(self.listing.top_bid, bid)

    def test_it_accepts_bid_exactly_at_the_minimum(self):
        # === Arrange === (10.00 is in the 0.50 tier, so the next minimum is 10.50)
        self.bid(self.alice, '10.00')

        # === Act ===
        bid = self.bid(self.bob, '10.50')

        # === Assert ===
        self.assertEqual(bid.amount, Decimal('10.50'))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.bids_count, 2)
        self.assertEqual(self.listing.top_bid, bid)

    def test_it_rejects_bid_one_cent_below_the_minimum(self):
        # === Arrange ===
        self.bid(self.alice, '10.00')
        before = self.snapshot()

        # === Act ===
        error = self.assert_rejected('bid_too_low', self.bob, '10.49')

        # === Assert ===
        self.assertEqual(error.min_bid, Decimal('10.50'))
        self.assertEqual(self.snapshot(), before)

    def test_it_rejects_bid_equal_to_the_current_price(self):
        # === Arrange ===
        self.bid(self.alice, '10.00')

        # === Act & Assert ===
        self.assert_rejected('bid_too_low', self.bob, '10.00')

    def test_it_uses_the_increment_of_the_current_price_tier(self):
        # === Arrange === (99.50 is in the 1.00 tier)
        self.bid(self.alice, '99.50')

        # === Act & Assert ===
        self.assert_rejected('bid_too_low', self.bob, '100.49')
        self.assertEqual(self.bid(self.bob, '100.50').amount, Decimal('100.50'))

    def test_it_allows_a_bidder_to_bid_again_after_being_outbid(self):
        # === Arrange ===
        self.bid(self.alice, '10.00')
        self.bid(self.bob, '11.00')

        # === Act ===
        bid = self.bid(self.alice, '12.00')

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.top_bid, bid)
        self.assertEqual(self.listing.bids_count, 3)

    # --- who can bid ---------------------------------------------------------------------

    def test_it_rejects_the_seller(self):
        # === Act ===
        self.assert_rejected('own_listing', self.seller, '10.00')

        # === Assert ===
        self.assertEqual(Bid.objects.count(), 0)

    def test_it_rejects_the_current_top_bidder(self):
        # === Arrange ===
        self.bid(self.alice, '10.00')
        before = self.snapshot()

        # === Act ===
        self.assert_rejected('already_top_bidder', self.alice, '20.00')

        # === Assert ===
        self.assertEqual(self.snapshot(), before)

    def test_it_checks_the_seller_before_the_amount(self):
        # === Act & Assert === (the amount is too low too, but the first broken rule is reported)
        self.assert_rejected('own_listing', self.seller, '1.00')

    # --- is the auction open -------------------------------------------------------------

    def test_it_rejects_bids_unless_the_listing_is_active(self):
        for value in (Listing.Status.DRAFT, Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=value):
                # === Arrange ===
                listing = make_listing(seller=self.seller, status=value, ends_at=NOW + timedelta(days=1))

                # === Act & Assert ===
                self.assert_rejected('auction_closed', self.alice, '10.00', listing=listing)
                self.assertEqual(Bid.objects.count(), 0)

    def test_it_rejects_bid_after_ends_at_even_if_the_task_has_not_closed_the_listing_yet(self):
        # === Arrange === (status is still active: the closing task lags behind)
        now = self.listing.ends_at + timedelta(seconds=1)

        # === Act & Assert ===
        self.assert_rejected('auction_closed', self.alice, '10.00', now=now)
        self.assertEqual(Bid.objects.count(), 0)

    def test_it_rejects_bid_at_the_exact_moment_the_auction_ends(self):
        # === Act & Assert ===
        self.assert_rejected('auction_closed', self.alice, '10.00', now=self.listing.ends_at)

    def test_it_accepts_bid_one_second_before_the_end(self):
        # === Act ===
        bid = self.bid(self.alice, '10.00', now=self.listing.ends_at - timedelta(seconds=1))

        # === Assert ===
        self.assertEqual(bid.amount, Decimal('10.00'))

    # --- the amount ----------------------------------------------------------------------

    def test_it_rejects_amounts_that_are_not_money(self):
        for value in ('0', '0.00', '-5', '10.005', '10.001', '10000000000.00'):
            with self.subTest(amount=value):
                self.assert_rejected('invalid_amount', self.alice, value)
        self.assertEqual(Bid.objects.count(), 0)

    def test_it_rejects_unknown_listing(self):
        with self.assertRaises(Listing.DoesNotExist):
            place_bid(999999, self.alice, Decimal('10.00'), now=NOW)

    # --- anti-sniping --------------------------------------------------------------------

    def test_it_does_not_change_ends_at_for_a_bid_well_before_the_end(self):
        # === Arrange ===
        ends_at = self.listing.ends_at

        # === Act ===
        self.bid(self.alice, '10.00', now=ends_at - SNIPING_WINDOW - timedelta(seconds=1))

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.ends_at, ends_at)

    def test_it_extends_the_auction_for_a_bid_in_the_last_two_minutes(self):
        # === Arrange ===
        now = self.listing.ends_at - timedelta(seconds=30)

        # === Act ===
        self.bid(self.alice, '10.00', now=now)

        # === Assert === (the auction now ends two minutes after the bid)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.ends_at, now + SNIPING_WINDOW)

    def test_it_keeps_ends_at_for_a_bid_exactly_two_minutes_before_the_end(self):
        # === Arrange ===
        ends_at = self.listing.ends_at

        # === Act === (now + 2 minutes is exactly ends_at, so nothing moves)
        self.bid(self.alice, '10.00', now=ends_at - SNIPING_WINDOW)

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.ends_at, ends_at)

    def test_it_extends_again_for_every_late_bid(self):
        # === Arrange ===
        first_now = self.listing.ends_at - timedelta(seconds=10)
        self.bid(self.alice, '10.00', now=first_now)
        self.listing.refresh_from_db()
        second_now = self.listing.ends_at - timedelta(seconds=5)

        # === Act ===
        self.bid(self.bob, '11.00', now=second_now)

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.ends_at, second_now + SNIPING_WINDOW)

    def test_it_accepts_a_late_bid_in_the_extension(self):
        # === Arrange === (a bid at the very end moves ends_at, a later one is still in time)
        late = self.listing.ends_at - timedelta(seconds=1)
        self.bid(self.alice, '10.00', now=late)

        # === Act ===
        bid = self.bid(self.bob, '11.00', now=late + timedelta(minutes=1))

        # === Assert ===
        self.assertEqual(bid.amount, Decimal('11.00'))

    def test_it_does_not_extend_the_auction_for_a_rejected_late_bid(self):
        # === Arrange ===
        ends_at = self.listing.ends_at

        # === Act ===
        self.assert_rejected('bid_too_low', self.alice, '5.00', now=ends_at - timedelta(seconds=10))

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.ends_at, ends_at)
