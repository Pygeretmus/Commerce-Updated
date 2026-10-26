from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing
from ..services.bidding import place_bid
from ..services.closing import close_expired
from .helpers import bid_on, make_active_listing

User = get_user_model()


class APIMyBidsViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.me = G(User)
        cls.rival = G(User)

    def setUp(self):
        self.url = reverse('listings:me-bids')
        self.client.force_authenticate(self.me)

    def lot(self, **kwargs) -> Listing:
        return make_active_listing(seller=self.seller, starting_price=Decimal(10), **kwargs)

    def statuses(self, query: str = '') -> dict[int, str]:
        rows = self.client.get(self.url + query).json()['results']
        return {row['id']: row['my_status'] for row in rows}

    def finish(self, listing: Listing) -> None:
        Listing.objects.filter(pk=listing.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        close_expired(listing.pk)

    def test_it_requires_authentication(self):
        # === Arrange ===
        self.client.force_authenticate(None)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_computes_the_status_of_each_lot(self):
        # === Arrange ===
        winning, outbid, won, lost = self.lot(), self.lot(), self.lot(), self.lot()
        bid_on(winning, self.me, '10.00')
        bid_on(outbid, self.me, '10.00')
        bid_on(outbid, self.rival, '11.00')
        bid_on(won, self.me, '10.00')
        bid_on(lost, self.me, '10.00')
        bid_on(lost, self.rival, '11.00')
        self.finish(won)
        self.finish(lost)

        # === Act ===
        result = self.statuses()

        # === Assert ===
        self.assertEqual(result, {winning.pk: 'winning', outbid.pk: 'outbid', won.pk: 'won', lost.pk: 'lost'})

    def test_it_counts_a_lot_as_lost_when_the_reserve_was_not_met(self):
        # === Arrange ===
        listing = self.lot(reserve_price=Decimal(100))
        bid_on(listing, self.me, '10.00')
        self.finish(listing)

        # === Act & Assert ===
        self.assertEqual(self.statuses(), {listing.pk: 'lost'})

    def test_it_returns_one_row_per_lot_with_my_highest_bid(self):
        # === Arrange ===
        listing = self.lot()
        bid_on(listing, self.me, '10.00')
        bid_on(listing, self.rival, '11.00')
        bid_on(listing, self.me, '12.00')

        # === Act ===
        rows = self.client.get(self.url).json()['results']

        # === Assert ===
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['my_highest_bid'], rows[0]['current_price']), ('12.00', '12.00'))

    def test_it_ignores_lots_I_did_not_bid_on(self):
        # === Arrange ===
        self.lot()
        other = self.lot()
        bid_on(other, self.rival, '10.00')

        # === Act & Assert ===
        self.assertEqual(self.statuses(), {})

    def test_it_filters_by_status(self):
        # === Arrange ===
        winning, outbid = self.lot(), self.lot()
        bid_on(winning, self.me, '10.00')
        bid_on(outbid, self.me, '10.00')
        bid_on(outbid, self.rival, '11.00')

        # === Act & Assert ===
        self.assertEqual(self.statuses('?status=outbid'), {outbid.pk: 'outbid'})
        self.assertEqual(self.statuses('?status=winning'), {winning.pk: 'winning'})

    def test_it_rejects_an_unknown_status(self):
        # === Act ===
        response = self.client.get(self.url + '?status=bogus')

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_orders_by_my_latest_bid(self):
        # === Arrange ===
        first, second = self.lot(), self.lot()
        bid_on(first, self.me, '10.00')
        bid_on(second, self.me, '10.00')

        # === Act ===
        rows = self.client.get(self.url).json()['results']

        # === Assert ===
        self.assertEqual([row['id'] for row in rows], [second.pk, first.pk])

    def test_it_uses_a_fixed_number_of_queries(self):
        # === Arrange ===
        for _ in range(8):
            bid_on(self.lot(), self.me, '10.00')

        # === Act & Assert === (count, rows, images)
        with self.assertNumQueries(3):
            self.client.get(self.url)

    def test_it_keeps_working_after_place_bid_by_the_rival(self):
        # === Arrange ===
        listing = self.lot()
        bid_on(listing, self.me, '10.00')

        # === Act ===
        place_bid(listing.pk, self.rival, Decimal('11.00'))

        # === Assert ===
        self.assertEqual(self.statuses(), {listing.pk: 'outbid'})
