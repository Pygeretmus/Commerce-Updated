from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Bid, Listing
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()


class APIBidCreateViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.alice = G(User, username='alice')
        cls.bob = G(User, username='bobby')

    def setUp(self):
        cache.clear()
        self.listing = make_active_listing(seller=self.seller, starting_price=Decimal(10))
        self.url = reverse('listings:bid-list', args=[self.listing.pk])

    def test_it_places_a_bid_and_returns_the_new_state(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(self.url, {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['bid']['amount'], '10.00')
        self.assertEqual(data['bid']['bidder'], 'alice')  # my own bid shows my real name
        self.assertTrue(data['bid']['is_mine'])
        self.assertEqual(data['state']['current_price'], '10.00')
        self.assertEqual(data['state']['bids_count'], 1)
        self.assertEqual(data['state']['next_min_bid'], '10.50')
        self.assertEqual(data['state']['leader'], 'a***e')  # everybody else sees the masked name
        self.assertEqual(Bid.objects.get().bidder, self.alice)

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.post(self.url, {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Bid.objects.count(), 0)

    def test_it_rejects_a_bid_that_is_too_low_with_the_minimum_in_the_message(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        self.client.force_authenticate(self.bob)

        # === Act ===
        response = self.client.post(self.url, {'amount': '10.20'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.json()['errors'][0]
        self.assertEqual(error['code'], 'bid_too_low')
        self.assertIn('10.50', error['message'])

    def test_it_rejects_the_seller(self):
        # === Arrange ===
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(self.url, {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'own_listing')

    def test_it_rejects_the_current_leader(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(self.url, {'amount': '20.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'already_top_bidder')

    def test_it_rejects_a_bid_after_the_end_even_if_the_listing_is_still_active(self):
        # === Arrange ===
        Listing.objects.filter(pk=self.listing.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(self.url, {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'auction_closed')

    def test_it_rejects_invalid_amounts(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        for value in ('abc', '', '-5', '0', '10.123', '99999999999'):
            with self.subTest(amount=value):
                # === Act ===
                response = self.client.post(self.url, {'amount': value})

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()['errors'][0]['param'], 'amount')

    def test_it_requires_the_amount(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(self.url, {})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_returns_not_found_for_a_draft_of_somebody_else(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(reverse('listings:bid-list', args=[draft.pk]), {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_not_found_for_unknown_listing(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(reverse('listings:bid-list', args=[999999]), {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_extends_the_auction_for_a_late_bid(self):
        # === Arrange ===
        soon = timezone.now() + timedelta(seconds=30)
        Listing.objects.filter(pk=self.listing.pk).update(ends_at=soon)
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(self.url, {'amount': '10.00'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.listing.refresh_from_db()
        self.assertGreater(self.listing.ends_at, soon + timedelta(seconds=60))

    def test_it_throttles_bids(self):
        from unittest import mock

        from rest_framework.throttling import ScopedRateThrottle

        # === Arrange ===
        self.client.force_authenticate(self.alice)

        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'bid': '2/min'}):
            # === Act ===
            codes = [self.client.post(self.url, {'amount': '1'}).status_code for _ in range(3)]

        # === Assert === (the first two are answered, the third is throttled before any rule is checked)
        self.assertEqual(codes[:2], [status.HTTP_400_BAD_REQUEST] * 2)
        self.assertEqual(codes[2], status.HTTP_429_TOO_MANY_REQUESTS)
