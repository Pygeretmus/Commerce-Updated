from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from ..models import Listing
from ..services.closing import ListingStateConflict, cancel
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()

# The tests pass `now` to the services, but bids use the real clock, so NOW is taken from it
NOW = timezone.now().replace(microsecond=0)


class CancelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)

    def test_it_cancels_a_listing_without_bids(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)

        # === Act ===
        cancel(listing.pk, now=NOW)

        # === Assert ===
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.CANCELLED)
        self.assertEqual(listing.closed_at, NOW)
        self.assertFalse(listing.sold)

    def test_it_refuses_when_there_are_bids(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller, starting_price=Decimal(10))
        bid_on(listing, G(User), '10.00')

        # === Act & Assert ===
        with self.assertRaises(ListingStateConflict) as raised:
            cancel(listing.pk)
        self.assertEqual(raised.exception.get_codes(), 'has_bids')
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ACTIVE)

    def test_it_refuses_a_draft_and_a_finished_listing(self):
        for state in (Listing.Status.DRAFT, Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=state):
                # === Arrange ===
                listing = make_listing(seller=self.seller, status=state)

                # === Act & Assert ===
                with self.assertRaises(ListingStateConflict) as raised:
                    cancel(listing.pk)
                self.assertEqual(raised.exception.get_codes(), 'not_active')
