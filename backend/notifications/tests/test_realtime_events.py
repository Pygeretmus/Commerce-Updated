"""What reaches the channel layer when things happen: pushes wait for the commit and carry the right data."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from listings.models import Listing
from listings.services.bidding import BidRejected, place_bid
from listings.services.closing import cancel, close_expired, end_now
from listings.services.state import iso
from listings.tests.helpers import bid_on, make_active_listing

from ..models import Notification
from ..serializers import NotificationSerializer
from ..services import realtime
from ..services.realtime import listing_group, user_group

User = get_user_model()


class RealtimeEventsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.alice = G(User, username='alice')
        cls.bob = G(User, username='bobby')

    def setUp(self):
        self.listing = make_active_listing(seller=self.seller, starting_price=Decimal(10))
        patcher = mock.patch.object(realtime, '_send')
        self.send = patcher.start()
        self.addCleanup(patcher.stop)

    def sent_to(self, group: str) -> list[dict]:
        return [call.args[1] for call in self.send.call_args_list if call.args[0] == group]

    def test_it_pushes_the_new_price_to_the_listing_group_after_commit(self):
        # === Act ===
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            place_bid(self.listing.pk, self.alice, Decimal(10))

        # === Assert === (nothing is sent before the commit)
        self.send.assert_not_called()
        for callback in callbacks:
            callback()
        (event,) = self.sent_to(listing_group(self.listing.pk))
        self.assertEqual(
            (event['type'], event['listing_id'], event['current_price'], event['bids_count'], event['leader']),
            ('price_update', self.listing.pk, '10.00', 1, 'a***e'),
        )
        self.assertEqual(event['next_min_bid'], '10.50')

    def test_it_pushes_nothing_for_a_rejected_bid(self):
        # === Act ===
        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(BidRejected):
            place_bid(self.listing.pk, self.alice, Decimal(1))

        # === Assert ===
        self.send.assert_not_called()

    def test_it_pushes_the_extended_end_when_a_late_bid_moves_it(self):
        # === Arrange ===
        self.listing.ends_at = timezone.now() + timedelta(seconds=30)
        self.listing.save(update_fields=['ends_at'])

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.listing.pk, self.alice, Decimal(10))

        # === Assert ===
        self.listing.refresh_from_db()
        (event,) = self.sent_to(listing_group(self.listing.pk))
        self.assertEqual(event['ends_at'], iso(self.listing.ends_at))
        self.assertGreater(self.listing.ends_at, timezone.now() + timedelta(seconds=90))

    def test_it_pushes_the_winner_when_the_seller_ends_the_auction(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        bid_on(self.listing, self.bob, '10.50')
        self.send.reset_mock()

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            end_now(self.listing.pk)

        # === Assert ===
        (event,) = self.sent_to(listing_group(self.listing.pk))
        self.assertEqual(
            (event['type'], event['status'], event['sold'], event['final_price'], event['winner']),
            ('listing_ended', 'ended', True, '10.50', 'b***y'),
        )

    def test_it_pushes_an_unsold_end_without_a_winner_when_the_time_is_up(self):
        # === Arrange === (a reserve nobody reached)
        reserve_listing = make_active_listing(
            seller=self.seller, starting_price=Decimal(10), reserve_price=Decimal(100)
        )
        bid_on(reserve_listing, self.alice, '10.00')
        self.send.reset_mock()
        reserve_listing.refresh_from_db()

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            close_expired(reserve_listing.pk, reserve_listing.ends_at + timedelta(seconds=1))

        # === Assert ===
        (event,) = self.sent_to(listing_group(reserve_listing.pk))
        self.assertEqual(
            (event['type'], event['sold'], event['winner'], event['final_price']),
            ('listing_ended', False, None, '10.00'),
        )

    def test_it_pushes_the_outbid_notification_to_the_old_leader(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        self.send.reset_mock()

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.listing.pk, self.bob, Decimal('11.00'))

        # === Assert ===
        (event,) = self.sent_to(user_group(self.alice.pk))
        self.assertEqual((event['type'], event['kind']), ('notification', 'outbid'))
        self.assertIn('$11.00', event['text'])

    def test_a_pushed_notification_has_the_shape_of_the_rest_one(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        self.send.reset_mock()

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.listing.pk, self.bob, Decimal('11.00'))

        # === Assert === (same keys and same date format: the client needs one parser, not two)
        (event,) = self.sent_to(user_group(self.alice.pk))
        stored = Notification.objects.select_related('listing').get(recipient=self.alice)
        self.assertEqual({k: v for k, v in event.items() if k != 'type'}, dict(NotificationSerializer(stored).data))

    def test_it_pushes_the_won_notification_when_the_auction_ends(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        Listing.objects.filter(pk=self.listing.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.send.reset_mock()

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            close_expired(self.listing.pk)

        # === Assert ===
        (won,) = self.sent_to(user_group(self.alice.pk))
        self.assertEqual(won['kind'], 'won')

    def test_it_pushes_a_cancellation(self):
        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            cancel(self.listing.pk)

        # === Assert ===
        (event,) = self.sent_to(listing_group(self.listing.pk))
        self.assertEqual((event['status'], event['sold']), ('cancelled', False))
