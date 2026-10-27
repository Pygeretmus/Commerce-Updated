from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django_dynamic_fixture import G

from listings.tests.helpers import make_active_listing

from ..models import Notification
from ..services.notify import notify

User = get_user_model()


class NotifyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = G(User)
        cls.bob = G(User)
        cls.listing = make_active_listing(seller=None, title='Blue vase')

    def test_it_creates_one_notification_per_recipient(self):
        # === Act ===
        created = notify([self.alice.pk, self.bob.pk, self.alice.pk], Notification.Kind.LOST, self.listing)

        # === Assert ===
        self.assertEqual(len(created), 2)
        self.assertCountEqual(Notification.objects.values_list('recipient', flat=True), [self.alice.pk, self.bob.pk])

    def test_it_skips_deleted_accounts(self):
        # === Act ===
        created = notify([None, self.alice.pk, None], Notification.Kind.LOST, self.listing)

        # === Assert ===
        self.assertEqual(len(created), 1)

    def test_it_creates_nothing_for_nobody(self):
        # === Act & Assert ===
        self.assertEqual(notify([], Notification.Kind.LOST, self.listing), [])
        self.assertEqual(notify([None], Notification.Kind.LOST, self.listing), [])
        self.assertEqual(Notification.objects.count(), 0)

    def test_it_stores_amounts_as_text(self):
        # === Act ===
        notify([self.alice.pk], Notification.Kind.OUTBID, self.listing, amount=Decimal('12.5'))

        # === Assert ===
        self.assertEqual(Notification.objects.get().data, {'amount': '12.50'})

    def test_it_is_rolled_back_together_with_the_transaction(self):
        # === Act ===
        try:
            with transaction.atomic():
                notify([self.alice.pk], Notification.Kind.LOST, self.listing)
                raise RuntimeError('the bid failed')
        except RuntimeError:
            pass

        # === Assert ===
        self.assertEqual(Notification.objects.count(), 0)

    def test_it_allows_only_one_ending_soon_per_person_and_listing(self):
        # === Arrange ===
        notify([self.alice.pk], Notification.Kind.ENDING_SOON, self.listing)

        # === Act & Assert ===
        # (PostgreSQL names the constraint, SQLite names the columns)
        constraint = 'notification_one_ending_soon|notifications_notification.listing_id'
        with self.assertRaisesRegex(IntegrityError, constraint), transaction.atomic():
            notify([self.alice.pk], Notification.Kind.ENDING_SOON, self.listing)

    def test_it_allows_many_outbid_notifications_for_one_listing(self):
        # === Act ===
        for amount in ('11.00', '12.00'):
            notify([self.alice.pk], Notification.Kind.OUTBID, self.listing, amount=amount)

        # === Assert ===
        self.assertEqual(Notification.objects.count(), 2)
