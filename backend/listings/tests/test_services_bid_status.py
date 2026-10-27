from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_dynamic_fixture import G

from ..models import Listing
from ..services.closing import close_expired, end_now
from ..services.state import bid_status
from .helpers import bid_on, make_active_listing

User = get_user_model()


class BidStatusTest(TestCase):
    """The detail page (Python) and the "my bids" list (SQL) must tell a bidder the same thing."""

    @classmethod
    def setUpTestData(cls):
        cls.alice = G(User, username='alice')
        cls.bob = G(User, username='bobby')

    def assert_both_agree(self, listing, user, expected):
        in_python = bid_status(Listing.objects.select_related('top_bid').get(pk=listing.pk), user.pk)
        in_sql = Listing.objects.bid_on_by(user).get(pk=listing.pk).my_status
        self.assertEqual((in_python, in_sql), (expected, expected))

    def test_it_tells_who_leads_and_who_is_outbid_while_the_lot_runs(self):
        # === Arrange ===
        listing = make_active_listing(starting_price=Decimal(10))
        bid_on(listing, self.alice, '10.00')
        bid_on(listing, self.bob, '10.50')

        # === Act & Assert ===
        self.assert_both_agree(listing, self.bob, 'winning')
        self.assert_both_agree(listing, self.alice, 'outbid')

    def test_it_tells_who_won_and_who_lost_after_a_sale(self):
        # === Arrange ===
        listing = make_active_listing(starting_price=Decimal(10))
        bid_on(listing, self.alice, '10.00')
        bid_on(listing, self.bob, '10.50')

        # === Act ===
        end_now(listing.pk)

        # === Assert ===
        self.assert_both_agree(listing, self.bob, 'won')
        self.assert_both_agree(listing, self.alice, 'lost')

    def test_it_tells_everybody_they_lost_when_the_reserve_was_not_reached(self):
        # === Arrange ===
        listing = make_active_listing(starting_price=Decimal(10), reserve_price=Decimal(100))
        bid_on(listing, self.alice, '10.00')
        bid_on(listing, self.bob, '10.50')

        # === Act ===
        listing.refresh_from_db()
        close_expired(listing.pk, listing.ends_at + timedelta(seconds=1))

        # === Assert === (the top bidder did not win either: the lot was not sold)
        self.assert_both_agree(listing, self.bob, 'lost')
        self.assert_both_agree(listing, self.alice, 'lost')
