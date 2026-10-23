from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from listings import tasks
from listings.models import Listing
from listings.tests.helpers import make_active_listing, make_listing

User = get_user_model()


class CloseExpiredListingsTaskTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)

    def test_it_closes_only_expired_active_listings(self):
        # === Arrange ===
        expired = make_active_listing(seller=self.seller, ends_at=timezone.now() - timedelta(minutes=1))
        running = make_active_listing(seller=self.seller, ends_at=timezone.now() + timedelta(minutes=1))
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)

        # === Act ===
        closed = tasks.close_expired_listings()

        # === Assert ===
        self.assertEqual(closed, 1)
        statuses = {pk: Listing.objects.get(pk=pk).status for pk in (expired.pk, running.pk, draft.pk)}
        self.assertEqual(
            statuses,
            {expired.pk: Listing.Status.ENDED, running.pk: Listing.Status.ACTIVE, draft.pk: Listing.Status.DRAFT},
        )

    def test_it_is_harmless_to_run_twice(self):
        # === Arrange ===
        make_active_listing(seller=self.seller, ends_at=timezone.now() - timedelta(minutes=1))

        # === Act ===
        first, second = tasks.close_expired_listings(), tasks.close_expired_listings()

        # === Assert ===
        self.assertEqual((first, second), (1, 0))

    def test_one_failing_listing_does_not_block_the_others(self):
        # === Arrange ===
        bad = make_active_listing(seller=self.seller, ends_at=timezone.now() - timedelta(minutes=2))
        good = make_active_listing(seller=self.seller, ends_at=timezone.now() - timedelta(minutes=1))
        real = tasks.close_expired

        def flaky(listing_id, now):
            if listing_id == bad.pk:
                raise RuntimeError('boom')
            return real(listing_id, now)

        # === Act ===
        with mock.patch.object(tasks, 'close_expired', flaky), self.assertLogs('listings.tasks', 'ERROR'):
            closed = tasks.close_expired_listings()

        # === Assert ===
        self.assertEqual(closed, 1)
        self.assertEqual(Listing.objects.get(pk=good.pk).status, Listing.Status.ENDED)
        self.assertEqual(Listing.objects.get(pk=bad.pk).status, Listing.Status.ACTIVE)
