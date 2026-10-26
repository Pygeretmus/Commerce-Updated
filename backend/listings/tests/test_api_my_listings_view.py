from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing
from .helpers import make_active_listing, make_listing

User = get_user_model()


class APIMyListingsViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = G(User)
        cls.other = G(User)

    def setUp(self):
        self.url = reverse('listings:me-listings')
        self.client.force_authenticate(self.me)

    def ids(self, query: str = '') -> list[int]:
        return [row['id'] for row in self.client.get(self.url + query).json()['results']]

    def test_it_requires_authentication(self):
        # === Arrange ===
        self.client.force_authenticate(None)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_lists_only_my_listings_in_every_status_newest_first(self):
        # === Arrange ===
        draft = make_listing(seller=self.me, status=Listing.Status.DRAFT)
        active = make_active_listing(seller=self.me)
        make_active_listing(seller=self.other)

        # === Act & Assert ===
        self.assertEqual(self.ids(), [active.pk, draft.pk])

    def test_it_filters_by_status(self):
        # === Arrange ===
        make_listing(seller=self.me, status=Listing.Status.DRAFT)
        active = make_active_listing(seller=self.me)

        # === Act & Assert ===
        self.assertEqual(self.ids('?status=active'), [active.pk])

    def test_it_rejects_an_unknown_status(self):
        # === Act ===
        response = self.client.get(self.url + '?status=bogus')

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_shows_the_reserve_price_to_its_owner(self):
        # === Arrange ===
        from decimal import Decimal

        make_active_listing(seller=self.me, starting_price=Decimal(10), reserve_price=Decimal(50))

        # === Act ===
        row = self.client.get(self.url).json()['results'][0]

        # === Assert ===
        self.assertEqual(row['reserve_price'], '50.00')

    def test_it_uses_a_fixed_number_of_queries(self):
        # === Arrange ===
        for _ in range(6):
            make_active_listing(seller=self.me)

        # === Act & Assert === (count, rows, images)
        with self.assertNumQueries(3):
            self.client.get(self.url)
