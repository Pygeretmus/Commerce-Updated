from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()


class APIListingCancelViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def url(self, listing: Listing) -> str:
        return reverse('listings:listing-cancel', args=[listing.pk])

    def test_it_cancels_an_active_listing_without_bids(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'cancelled')
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.CANCELLED)

    def test_it_requires_authentication(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_forbids_other_users(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        self.client.force_authenticate(self.other)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ACTIVE)

    def test_it_returns_not_found_for_a_draft_of_somebody_else(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)
        self.client.force_authenticate(self.other)

        # === Act ===
        response = self.client.post(self.url(draft))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_answers_conflict_when_there_are_bids(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        bid_on(listing, self.other, listing.starting_price)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()['errors'][0]['code'], 'has_bids')

    def test_it_answers_conflict_for_a_draft_and_for_a_finished_listing(self):
        for state in (Listing.Status.DRAFT, Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=state):
                # === Arrange ===
                listing = make_listing(seller=self.seller, status=state)
                self.client.force_authenticate(self.seller)

                # === Act ===
                response = self.client.post(self.url(listing))

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                self.assertEqual(response.json()['errors'][0]['code'], 'not_active')
