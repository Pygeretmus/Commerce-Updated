from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing, Watch
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()


class APIMySummaryViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = G(User)
        cls.other = G(User)

    def setUp(self):
        self.url = reverse('listings:me-summary')

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_returns_zeros_for_a_new_user(self):
        # === Arrange ===
        self.client.force_authenticate(self.me)

        # === Act ===
        data = self.client.get(self.url).json()

        # === Assert ===
        self.assertEqual(
            data,
            {
                'bids': {'winning': 0, 'outbid': 0, 'won': 0, 'lost': 0},
                'listings': {'draft': 0, 'active': 0, 'ended': 0, 'cancelled': 0},
                'watching': 0,
            },
        )

    def test_it_counts_everything_for_the_current_user_only(self):
        # === Arrange ===
        make_listing(seller=self.me, status=Listing.Status.DRAFT)
        make_active_listing(seller=self.me)
        theirs = make_active_listing(seller=self.other, starting_price=Decimal(10))
        bid_on(theirs, self.me, '10.00')
        Watch.objects.create(user=self.me, listing=theirs)
        Watch.objects.create(user=self.other, listing=theirs)
        bid_on(theirs, G(User), '11.00')  # outbids me: one unread notification
        self.client.force_authenticate(self.me)

        # === Act ===
        data = self.client.get(self.url).json()

        # === Assert ===
        self.assertEqual(data['listings'], {'draft': 1, 'active': 1, 'ended': 0, 'cancelled': 0})
        self.assertEqual(data['bids'], {'winning': 0, 'outbid': 1, 'won': 0, 'lost': 0})
        self.assertEqual(data['watching'], 1)
