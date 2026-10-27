from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from ..models import Listing
from ..services.closing import ListingStateConflict, end_now
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()

# The tests pass `now` to the services, but bids use the real clock, so NOW is taken from it
NOW = timezone.now().replace(microsecond=0)


class EndNowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.alice = G(User)

    def test_it_sells_to_the_top_bidder_even_if_the_reserve_is_not_met(self):
        # === Arrange === (the seller chose to accept the offer)
        listing = make_active_listing(seller=self.seller, starting_price=Decimal(10), reserve_price=Decimal(100))
        bid_on(listing, self.alice, '12.00')

        # === Act ===
        end_now(listing.pk, now=NOW)

        # === Assert ===
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ENDED)
        self.assertTrue(listing.sold)
        self.assertEqual(listing.closed_at, NOW)
        self.assertLessEqual(listing.ends_at, NOW)

    def test_it_needs_a_bid(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)

        # === Act & Assert ===
        with self.assertRaises(ListingStateConflict) as raised:
            end_now(listing.pk)
        self.assertEqual(raised.exception.get_codes(), 'no_bids')

    def test_it_needs_an_active_listing(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller, status=Listing.Status.ENDED)

        # === Act & Assert ===
        with self.assertRaises(ListingStateConflict) as raised:
            end_now(listing.pk)
        self.assertEqual(raised.exception.get_codes(), 'not_active')
