from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()


class APIBidListViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.alice = G(User, username='alice')
        cls.bob = G(User, username='bobby')

    def setUp(self):
        self.listing = make_active_listing(seller=self.seller, starting_price=Decimal(10))
        self.url = reverse('listings:bid-list', args=[self.listing.pk])

    def test_it_lists_bids_from_the_highest_with_masked_names(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        bid_on(self.listing, self.bob, '11.00')

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()['results']
        self.assertEqual([r['amount'] for r in rows], ['11.00', '10.00'])
        self.assertEqual([r['bidder'] for r in rows], ['b***y', 'a***e'])
        self.assertEqual([r['is_mine'] for r in rows], [False, False])

    def test_it_shows_my_own_bids_with_my_real_name(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')
        bid_on(self.listing, self.bob, '11.00')
        self.client.force_authenticate(self.alice)

        # === Act ===
        rows = self.client.get(self.url).json()['results']

        # === Assert ===
        self.assertEqual([(r['bidder'], r['is_mine']) for r in rows], [('b***y', False), ('alice', True)])

    def test_it_never_exposes_emails_or_user_ids(self):
        # === Arrange ===
        bid_on(self.listing, self.alice, '10.00')

        # === Act ===
        row = self.client.get(self.url).json()['results'][0]

        # === Assert ===
        self.assertEqual(set(row), {'id', 'bidder', 'amount', 'created_at', 'is_mine'})

    def test_it_shows_a_deleted_bidder_as_null(self):
        # === Arrange ===
        gone = G(User)
        bid_on(self.listing, gone, '10.00')
        gone.delete()

        # === Act ===
        row = self.client.get(self.url).json()['results'][0]

        # === Assert ===
        self.assertIsNone(row['bidder'])

    def test_it_paginates(self):
        # === Arrange ===
        for index in range(25):
            bid_on(self.listing, G(User), Decimal(10) + index * 5)

        # === Act ===
        data = self.client.get(self.url).json()

        # === Assert ===
        self.assertEqual(data['count'], 25)
        self.assertEqual(len(data['results']), 20)

    def test_it_uses_a_fixed_number_of_queries(self):
        # === Arrange ===
        for index in range(10):
            bid_on(self.listing, G(User), Decimal(10) + index * 5)

        # === Act & Assert === (listing, count, bids with bidders)
        with self.assertNumQueries(3):
            self.client.get(self.url)

    def test_it_returns_not_found_for_a_draft_of_somebody_else(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)

        # === Act ===
        response = self.client.get(reverse('listings:bid-list', args=[draft.pk]))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
