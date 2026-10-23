from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G, N

from ..models import Bid, Category, Listing
from ..services.bidding import place_bid


class ListingConstraintsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.get(slug='art')

    def make_listing(self, **kwargs) -> Listing:
        listing = N(Listing, category=self.category, **kwargs)
        listing.save()
        return listing

    def test_it_creates_draft_by_default(self):
        # === Act ===
        listing = self.make_listing()

        # === Assert ===
        self.assertEqual(listing.status, 'draft')
        self.assertIsNone(listing.ends_at)

    def test_it_rejects_zero_starting_price(self):
        # === Act & Assert ===
        with self.assertRaisesMessage(IntegrityError, 'listing_starting_price_positive'), transaction.atomic():
            self.make_listing(starting_price=Decimal(0))
        self.assertEqual(Listing.objects.count(), 0)

    def test_it_rejects_negative_starting_price(self):
        with self.assertRaisesMessage(IntegrityError, 'listing_starting_price_positive'), transaction.atomic():
            self.make_listing(starting_price=Decimal(-1))
        self.assertEqual(Listing.objects.count(), 0)

    def test_it_rejects_reserve_price_below_starting_price(self):
        with self.assertRaisesMessage(IntegrityError, 'listing_reserve_gte_starting'), transaction.atomic():
            self.make_listing(starting_price=Decimal(10), reserve_price=Decimal('9.99'))
        self.assertEqual(Listing.objects.count(), 0)

    def test_it_allows_reserve_price_equal_to_starting_price(self):
        listing = self.make_listing(starting_price=Decimal(10), reserve_price=Decimal(10))

        self.assertEqual(listing.reserve_price, Decimal(10))

    def test_it_rejects_active_listing_without_ends_at(self):
        with self.assertRaisesMessage(IntegrityError, 'listing_active_has_ends_at'), transaction.atomic():
            self.make_listing(status=Listing.Status.ACTIVE, ends_at=None)
        self.assertEqual(Listing.objects.count(), 0)

    def test_it_allows_active_listing_with_ends_at(self):
        listing = self.make_listing(status=Listing.Status.ACTIVE, ends_at=timezone.now() + timedelta(days=1))

        self.assertEqual(listing.status, 'active')

    def test_it_protects_category_with_listings(self):
        self.make_listing()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.category.delete()
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_it_keeps_listing_when_seller_is_deleted(self):
        seller = G(get_user_model())
        listing = self.make_listing(seller=seller)

        seller.delete()

        listing.refresh_from_db()
        self.assertIsNone(listing.seller)

    def test_it_sets_current_price_to_starting_price_while_there_are_no_bids(self):
        # === Act ===
        listing = self.make_listing(starting_price=Decimal('12.50'))

        # === Assert ===
        self.assertEqual(listing.current_price, Decimal('12.50'))
        self.assertEqual(listing.bids_count, 0)
        self.assertIsNone(listing.top_bid)

    def test_it_follows_the_starting_price_when_it_is_saved_with_update_fields(self):
        # === Arrange ===
        listing = self.make_listing(starting_price=Decimal('10.00'))

        # === Act ===
        listing.starting_price = Decimal('20.00')
        listing.save(update_fields=['starting_price'])

        # === Assert ===
        listing.refresh_from_db()
        self.assertEqual(listing.current_price, Decimal('20.00'))

    def test_it_rejects_current_price_below_starting_price(self):
        # === Arrange ===
        listing = self.make_listing(starting_price=Decimal('10.00'))

        # === Act & Assert === (queryset.update() skips save(), so the database is the only guard)
        with self.assertRaisesMessage(IntegrityError, 'listing_current_price_gte_starting'), transaction.atomic():
            Listing.objects.filter(pk=listing.pk).update(current_price=Decimal('9.99'))

    def test_it_rejects_bids_count_without_top_bid(self):
        # === Arrange ===
        listing = self.make_listing()

        # === Act & Assert ===
        with self.assertRaisesMessage(IntegrityError, 'listing_top_bid_matches_bids_count'), transaction.atomic():
            Listing.objects.filter(pk=listing.pk).update(bids_count=1)

    def test_it_rejects_top_bid_without_bids_count(self):
        # === Arrange ===
        listing = self.make_listing()
        bid = Bid.objects.create(listing=listing, bidder=None, amount=listing.starting_price)

        # === Act & Assert ===
        with self.assertRaisesMessage(IntegrityError, 'listing_top_bid_matches_bids_count'), transaction.atomic():
            Listing.objects.filter(pk=listing.pk).update(top_bid=bid)

    def test_it_deletes_a_listing_together_with_its_bids(self):
        # === Arrange ===
        listing = self.make_listing(status=Listing.Status.ACTIVE, ends_at=timezone.now() + timedelta(days=1))
        place_bid(listing.pk, G(get_user_model()), listing.starting_price)

        # === Act ===
        Listing.objects.get(pk=listing.pk).delete()

        # === Assert ===
        self.assertEqual(Bid.objects.count(), 0)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())
