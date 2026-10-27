from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from listings.models import Listing, Watch
from listings.tests.helpers import bid_on, make_active_listing

from ..models import Notification
from ..services import notify_listing_ending_soon
from ..tasks import notify_ending_soon

User = get_user_model()


class NotifyEndingSoonTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.watcher = G(User)
        cls.bidder = G(User)

    def lot(self, minutes: int) -> Listing:
        return make_active_listing(
            seller=self.seller, starting_price=Decimal(10), ends_at=timezone.now() + timedelta(minutes=minutes)
        )

    def test_it_tells_watchers_and_bidders_once(self):
        # === Arrange ===
        listing = self.lot(30)
        Watch.objects.create(user=self.watcher, listing=listing)
        bid_on(listing, self.bidder, '10.00')
        Notification.objects.all().delete()

        # === Act ===
        first = notify_ending_soon()
        second = notify_ending_soon()

        # === Assert ===
        self.assertEqual((first, second), (2, 0))
        self.assertCountEqual(
            Notification.objects.filter(kind='ending_soon').values_list('recipient', flat=True),
            [self.watcher.pk, self.bidder.pk],
        )

    def test_it_never_tells_the_seller(self):
        # === Arrange ===
        listing = self.lot(30)
        Watch.objects.create(user=self.seller, listing=listing)

        # === Act ===
        notify_ending_soon()

        # === Assert ===
        self.assertEqual(Notification.objects.count(), 0)

    def test_it_ignores_lots_that_end_later_than_an_hour_or_have_ended(self):
        # === Arrange ===
        far = self.lot(61)
        gone = self.lot(-1)
        for listing in (far, gone):
            Watch.objects.create(user=self.watcher, listing=listing)

        # === Act ===
        total = notify_ending_soon()

        # === Assert ===
        self.assertEqual(total, 0)

    def test_it_announces_a_lot_that_enters_the_window_later(self):
        # === Arrange ===
        listing = self.lot(90)
        Watch.objects.create(user=self.watcher, listing=listing)
        self.assertEqual(notify_ending_soon(), 0)

        # === Act ===
        Listing.objects.filter(pk=listing.pk).update(ends_at=timezone.now() + timedelta(minutes=50))

        # === Assert ===
        self.assertEqual(notify_ending_soon(), 1)

    def test_it_does_not_repeat_when_called_directly_twice(self):
        # === Arrange ===
        listing = self.lot(30)
        Watch.objects.create(user=self.watcher, listing=listing)

        # === Act ===
        first = notify_listing_ending_soon(listing.pk)
        second = notify_listing_ending_soon(listing.pk)

        # === Assert ===
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(Notification.objects.count(), 1)
