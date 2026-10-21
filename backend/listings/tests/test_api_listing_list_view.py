from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Category, ListingImage
from .helpers import make_active_listing

User = get_user_model()


class APIListingListViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.get(slug='art')
        cls.seller = G(User, username='seller')

    def setUp(self):
        cache.clear()
        self.url = reverse('listings:listing-list')

    def test_it_returns_listing_data_to_anonymous_user(self):
        # === Arrange ===
        listing = make_active_listing(title='Vase', category=self.category, seller=self.seller)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['results'],
            [
                {
                    'id': listing.pk,
                    'title': 'Vase',
                    'starting_price': f'{listing.starting_price:.2f}',
                    'current_price': f'{listing.starting_price:.2f}',
                    'status': 'active',
                    'published_at': listing.published_at.isoformat().replace('+00:00', 'Z'),
                    'ends_at': listing.ends_at.isoformat().replace('+00:00', 'Z'),
                    'category': {'name': 'Art', 'slug': 'art'},
                    'seller': 'seller',
                    'cover': None,
                }
            ],
        )

    def test_it_paginates_results(self):
        # === Arrange ===
        for _ in range(5):
            make_active_listing()

        # === Act ===
        response = self.client.get(self.url, {'page_size': 2, 'page': 2})

        # === Assert ===
        data = response.json()
        self.assertEqual(data['count'], 5)
        self.assertEqual(len(data['results']), 2)
        self.assertIsNotNone(data['next'])
        self.assertIsNotNone(data['previous'])

    def test_it_limits_page_size(self):
        # === Arrange ===
        for _ in range(3):
            make_active_listing()

        # === Act ===
        response = self.client.get(self.url, {'page_size': 1000})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['results']), 3)

    def test_it_returns_null_seller_if_account_was_deleted(self):
        # === Arrange ===
        make_active_listing(seller=None)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertIsNone(response.json()['results'][0]['seller'])

    def test_it_returns_first_image_by_position_as_cover(self):
        # === Arrange ===
        listing = make_active_listing()
        ListingImage.objects.create(listing=listing, image='listings/second.jpg', position=1)
        ListingImage.objects.create(listing=listing, image='listings/first.jpg', position=0)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        cover = response.json()['results'][0]['cover']
        self.assertEqual(cover, 'http://testserver/media/listings/first.jpg')

    def test_it_uses_thumbnail_as_cover_when_it_is_ready(self):
        # === Arrange ===
        listing = make_active_listing()
        ListingImage.objects.create(
            listing=listing, image='listings/a.jpg', thumbnail='listings/thumbs/a.webp', position=0
        )

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.json()['results'][0]['cover'], 'http://testserver/media/listings/thumbs/a.webp')

    def test_it_does_not_increase_query_count_with_more_listings(self):
        # === Arrange ===
        listing = make_active_listing()
        ListingImage.objects.create(listing=listing, image='listings/a.jpg')
        with CaptureQueriesContext(connection) as one:
            self.client.get(self.url)

        for _ in range(29):
            other = make_active_listing(seller=G(User))
            ListingImage.objects.create(listing=other, image='listings/b.jpg')
            ListingImage.objects.create(listing=other, image='listings/c.jpg', position=1)

        # === Act ===
        with CaptureQueriesContext(connection) as many:
            response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(len(response.json()['results']), 20)  # first page
        self.assertEqual(len(many), len(one))
