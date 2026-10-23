from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from ..models import Listing
from ..services.closing import close_expired
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()

# The tests pass `now` to the services, but bids use the real clock, so NOW is taken from it
NOW = timezone.now().replace(microsecond=0)


class CloseExpiredTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.alice = G(User)
        cls.bob = G(User)

    def make(self, **kwargs) -> Listing:
        fields = {'seller': self.seller, 'starting_price': Decimal(10), 'ends_at': NOW}
        return make_active_listing(**(fields | kwargs))

    def test_it_does_nothing_before_ends_at(self):
        # === Arrange ===
        listing = self.make(ends_at=NOW + timedelta(seconds=1))

        # === Act ===
        closed = close_expired(listing.pk, now=NOW)

        # === Assert ===
        self.assertFalse(closed)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ACTIVE)

    def test_it_closes_exactly_at_ends_at(self):
        # === Arrange ===
        listing = self.make()

        # === Act ===
        closed = close_expired(listing.pk, now=NOW)

        # === Assert === (a bid at this very moment is rejected, so the auction is over)
        self.assertTrue(closed)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ENDED)
        self.assertEqual(listing.closed_at, NOW)

    def test_it_closes_after_ends_at(self):
        # === Arrange ===
        listing = self.make()

        # === Act ===
        closed = close_expired(listing.pk, now=NOW + timedelta(minutes=5))

        # === Assert ===
        self.assertTrue(closed)

    def test_it_is_idempotent(self):
        # === Arrange ===
        listing = self.make(ends_at=NOW + timedelta(days=1))
        bid_on(listing, self.alice, '10.00')
        Listing.objects.filter(pk=listing.pk).update(ends_at=NOW)
        close_expired(listing.pk, now=NOW)

        # === Act ===
        again = close_expired(listing.pk, now=NOW + timedelta(minutes=1))

        # === Assert === (no second result)
        self.assertFalse(again)
        listing.refresh_from_db()
        self.assertEqual(listing.closed_at, NOW)

    def test_it_ignores_unknown_and_non_active_listings(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)

        # === Act & Assert ===
        self.assertFalse(close_expired(999999, now=NOW))
        self.assertFalse(close_expired(draft.pk, now=NOW))

    def test_it_does_not_close_a_listing_extended_by_anti_sniping(self):
        # === Arrange === (ends at NOW; a bid 10 seconds before moves the end to two minutes after the bid)
        listing = self.make()
        bid_on_time = NOW - timedelta(seconds=10)
        from ..services.bidding import place_bid

        place_bid(listing.pk, self.alice, Decimal(10), now=bid_on_time)

        # === Act ===
        closed = close_expired(listing.pk, now=NOW + timedelta(seconds=30))

        # === Assert ===
        self.assertFalse(closed)

    def test_it_sells_to_the_top_bidder_when_there_is_no_reserve(self):
        # === Arrange ===
        listing = self.make(ends_at=NOW + timedelta(days=1))
        bid_on(listing, self.alice, '10.00')
        bid_on(listing, self.bob, '11.00')
        Listing.objects.filter(pk=listing.pk).update(ends_at=NOW)

        # === Act ===
        close_expired(listing.pk, now=NOW)

        # === Assert ===
        listing.refresh_from_db()
        self.assertTrue(listing.sold)
        self.assertEqual(listing.top_bid.bidder, self.bob)
        self.assertEqual(listing.current_price, Decimal('11.00'))

    def test_it_sells_when_the_reserve_is_met_exactly(self):
        # === Arrange ===
        listing = self.make(ends_at=NOW + timedelta(days=1), reserve_price=Decimal('11.00'))
        bid_on(listing, self.alice, '11.00')
        Listing.objects.filter(pk=listing.pk).update(ends_at=NOW)

        # === Act ===
        close_expired(listing.pk, now=NOW)

        # === Assert ===
        listing.refresh_from_db()
        self.assertTrue(listing.sold)

    def test_it_does_not_sell_when_the_reserve_is_not_met(self):
        # === Arrange ===
        listing = self.make(ends_at=NOW + timedelta(days=1), reserve_price=Decimal('50.00'))
        bid_on(listing, self.alice, '11.00')
        Listing.objects.filter(pk=listing.pk).update(ends_at=NOW)

        # === Act ===
        close_expired(listing.pk, now=NOW)

        # === Assert ===
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ENDED)
        self.assertFalse(listing.sold)

    def test_it_ends_unsold_when_there_are_no_bids(self):
        # === Arrange ===
        listing = self.make()

        # === Act ===
        close_expired(listing.pk, now=NOW)

        # === Assert ===
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ENDED)
        self.assertFalse(listing.sold)
