from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing, Watch
from .helpers import make_active_listing, make_listing

User = get_user_model()


class APIListingWatchViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.alice = G(User)

    def setUp(self):
        self.listing = make_active_listing(seller=self.seller)
        self.url = reverse('listings:listing-watch', args=[self.listing.pk])

    def test_it_adds_the_listing_to_the_watchlist(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.put(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Watch.objects.filter(user=self.alice, listing=self.listing).exists())

    def test_it_is_idempotent(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        self.client.put(self.url)
        response = self.client.put(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Watch.objects.count(), 1)

    def test_it_removes_the_listing_and_removing_twice_is_fine(self):
        # === Arrange ===
        Watch.objects.create(user=self.alice, listing=self.listing)
        self.client.force_authenticate(self.alice)

        # === Act ===
        first = self.client.delete(self.url)
        second = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual((first.status_code, second.status_code), (204, 204))
        self.assertEqual(Watch.objects.count(), 0)

    def test_it_does_not_touch_other_peoples_watchlists(self):
        # === Arrange ===
        bob = G(User)
        Watch.objects.create(user=bob, listing=self.listing)
        self.client.force_authenticate(self.alice)

        # === Act ===
        self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(Watch.objects.filter(user=bob).count(), 1)

    def test_it_requires_authentication(self):
        # === Act ===
        put, delete = self.client.put(self.url), self.client.delete(self.url)

        # === Assert ===
        self.assertEqual((put.status_code, delete.status_code), (401, 401))

    def test_it_returns_not_found_for_a_draft_and_for_an_unknown_listing(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)
        self.client.force_authenticate(self.seller)

        # === Act ===
        for pk in (draft.pk, 999999):
            response = self.client.put(reverse('listings:listing-watch', args=[pk]))

            # === Assert ===
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
