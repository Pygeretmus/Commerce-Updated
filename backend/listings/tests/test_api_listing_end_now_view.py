from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing
from .helpers import bid_on, make_active_listing, make_listing

User = get_user_model()


class APIListingEndNowViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.bidder = G(User, username='buyer')

    def url(self, listing: Listing) -> str:
        return reverse('listings:listing-end-now', args=[listing.pk])

    def test_it_ends_the_auction_and_the_top_bidder_wins(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        bid_on(listing, self.bidder, listing.starting_price)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual((data['status'], data['sold'], data['winner']), ('ended', True, 'b***r'))
        self.assertIsNotNone(data['closed_at'])

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
        bid_on(listing, self.bidder, listing.starting_price)
        self.client.force_authenticate(self.bidder)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_it_answers_conflict_without_bids(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()['errors'][0]['code'], 'no_bids')

    def test_it_answers_conflict_when_the_listing_is_not_active(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller, status=Listing.Status.ENDED)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()['errors'][0]['code'], 'not_active')
