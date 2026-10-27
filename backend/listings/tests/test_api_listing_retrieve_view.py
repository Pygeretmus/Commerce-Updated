from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Listing, ListingImage
from .helpers import make_active_listing, make_listing

User = get_user_model()


class APIListingRetrieveViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.other = G(User)

    def url(self, listing: Listing) -> str:
        return reverse('listings:listing-detail', args=[listing.pk])

    def test_it_returns_published_listing_to_anonymous_user(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller, title='Vase', reserve_price=None)

        # === Act ===
        response = self.client.get(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['id'], listing.pk)
        self.assertEqual(data['title'], 'Vase')
        self.assertEqual(data['description'], listing.description)
        self.assertEqual(data['status'], 'active')
        self.assertEqual(data['seller'], 'seller')
        self.assertEqual(data['category'], {'name': 'Art', 'slug': 'art'})
        self.assertFalse(data['has_reserve'])

    def test_it_returns_ended_and_cancelled_listings_to_anonymous_user(self):
        for value in (Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=value):
                # === Arrange ===
                listing = make_active_listing(seller=self.seller, status=value)

                # === Act ===
                response = self.client.get(self.url(listing))

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_it_returns_draft_to_its_seller(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller)
        self.client.force_authenticate(user=self.seller)

        # === Act ===
        response = self.client.get(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'draft')

    def test_it_returns_not_found_for_draft_to_other_user(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller)
        self.client.force_authenticate(user=self.other)

        # === Act ===
        response = self.client.get(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_not_found_for_draft_to_anonymous_user(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller)

        # === Act ===
        response = self.client.get(self.url(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_not_found_for_unknown_listing(self):
        # === Act ===
        response = self.client.get(reverse('listings:listing-detail', args=[999999]))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_shows_reserve_price_to_seller_only(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller, starting_price=10, reserve_price=50)

        # === Act & Assert ===
        self.client.force_authenticate(user=self.seller)
        seller_data = self.client.get(self.url(listing)).json()
        self.assertEqual(seller_data['reserve_price'], '50.00')
        self.assertTrue(seller_data['has_reserve'])

        for user in (self.other, None):
            with self.subTest(user=user):
                self.client.force_authenticate(user=user)
                data = self.client.get(self.url(listing)).json()
                self.assertNotIn('reserve_price', data)
                self.assertTrue(data['has_reserve'])

    def test_it_returns_images_ordered_by_position(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        second = ListingImage.objects.create(listing=listing, image='listings/b.jpg', position=1)
        first = ListingImage.objects.create(listing=listing, image='listings/a.jpg', position=0)

        # === Act ===
        response = self.client.get(self.url(listing))

        # === Assert ===
        self.assertEqual(
            response.json()['images'],
            [
                {'id': first.pk, 'url': 'http://testserver/media/listings/a.jpg', 'thumbnail': None, 'position': 0},
                {'id': second.pk, 'url': 'http://testserver/media/listings/b.jpg', 'thumbnail': None, 'position': 1},
            ],
        )

    def test_it_returns_thumbnail_url_when_it_is_ready(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        ListingImage.objects.create(
            listing=listing, image='listings/a.jpg', thumbnail='listings/thumbs/a.webp', position=0
        )

        # === Act ===
        response = self.client.get(self.url(listing))

        # === Assert ===
        image = response.json()['images'][0]
        self.assertEqual(image['url'], 'http://testserver/media/listings/a.jpg')
        self.assertEqual(image['thumbnail'], 'http://testserver/media/listings/thumbs/a.webp')

    def test_it_does_not_increase_query_count_with_more_images(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        ListingImage.objects.create(listing=listing, image='listings/a.jpg')
        with CaptureQueriesContext(connection) as one:
            self.client.get(self.url(listing))
        for position in range(1, 6):
            ListingImage.objects.create(listing=listing, image=f'listings/{position}.jpg', position=position)

        # === Act ===
        with CaptureQueriesContext(connection) as many:
            response = self.client.get(self.url(listing))

        # === Assert ===
        self.assertEqual(len(response.json()['images']), 6)
        self.assertEqual(len(many), len(one))
