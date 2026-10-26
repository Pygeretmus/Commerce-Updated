from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing
from ..services.closing import close_expired
from .helpers import bid_on, make_active_listing

User = get_user_model()


class APIListingRetrieveBiddingFieldsTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.alice = G(User, username='alice')
        cls.bob = G(User, username='bobby')

    def setUp(self):
        self.listing = make_active_listing(seller=self.seller, starting_price=Decimal(10))
        self.url = reverse('listings:listing-detail', args=[self.listing.pk])

    def get(self) -> dict:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_it_shows_the_state_of_a_lot_without_bids(self):
        # === Act ===
        data = self.get()

        # === Assert ===
        self.assertEqual(
            (data['current_price'], data['bids_count'], data['next_min_bid'], data['leader']),
            ('10.00', 0, '10.00', None),
        )
        self.assertFalse(data['is_ended'])
        self.assertGreater(data['seconds_left'], 0)
        self.assertIsNotNone(data['server_time'])
        self.assertEqual((data['is_seller'], data['is_watching'], data['my_bid_status']), (False, False, None))
        self.assertEqual((data['sold'], data['winner']), (None, None))

    def test_it_shows_the_price_leader_and_minimum_after_bids(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        bid_on(self.listing, self.bob, '12.00')

        # === Act ===
        data = self.get()

        # === Assert ===
        self.assertEqual(
            (data['current_price'], data['bids_count'], data['next_min_bid'], data['leader']),
            ('12.00', 2, '12.50', 'b***y'),
        )

    def test_it_tells_me_my_bid_status(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        self.client.force_authenticate(self.alice)

        # === Act & Assert ===
        self.assertEqual(self.get()['my_bid_status'], 'winning')
        bid_on(self.listing, self.bob, '11.00')
        self.assertEqual(self.get()['my_bid_status'], 'outbid')

    def test_it_says_whether_the_secret_reserve_is_met_but_never_its_value(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller, starting_price=Decimal(10), reserve_price=Decimal(50))
        url = reverse('listings:listing-detail', args=[listing.pk])
        bid_on(listing, self.alice, '10.00')

        # === Act ===
        before = self.client.get(url).json()
        bid_on(listing, self.bob, '50.00')
        after = self.client.get(url).json()

        # === Assert ===
        self.assertEqual((before['has_reserve'], before['reserve_met']), (True, False))
        self.assertTrue(after['reserve_met'])
        self.assertNotIn('reserve_price', after)
        self.assertIsNone(self.get()['reserve_met'])  # a lot without a reserve says nothing

    def test_it_treats_a_lot_past_its_end_as_ended_before_the_closing_task_runs(self):
        # === Arrange ===
        Listing.objects.filter(pk=self.listing.pk).update(ends_at=timezone.now() - timedelta(seconds=5))

        # === Act ===
        data = self.get()

        # === Assert ===
        self.assertEqual(data['status'], 'active')
        self.assertTrue(data['is_ended'])
        self.assertEqual(data['seconds_left'], 0)

    def test_it_shows_the_result_of_a_closed_auction(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        Listing.objects.filter(pk=self.listing.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        close_expired(self.listing.pk)
        self.client.force_authenticate(self.alice)

        # === Act ===
        data = self.get()

        # === Assert ===
        self.assertEqual(
            (data['status'], data['sold'], data['winner'], data['my_bid_status']), ('ended', True, 'a***e', 'won')
        )
        self.assertIsNone(data['seconds_left'])
        self.assertIsNotNone(data['closed_at'])

    def test_it_uses_a_fixed_number_of_queries(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        self.client.force_authenticate(self.bob)

        # === Act & Assert === (the lot with seller, category, leader and my flags in one query, then the images)
        with self.assertNumQueries(2):
            self.client.get(self.url)
