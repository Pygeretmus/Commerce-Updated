from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Category, Listing, ListingImage
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
                    'bids_count': 0,
                    'status': 'active',
                    'is_ended': False,
                    'published_at': listing.published_at.isoformat().replace('+00:00', 'Z'),
                    'ends_at': listing.ends_at.isoformat().replace('+00:00', 'Z'),
                    'category': {'name': 'Art', 'slug': 'art'},
                    'seller': 'seller',
                    'sold': None,
                    'cover': None,
                }
            ],
        )

    def test_it_returns_only_active_listings_by_default(self):
        # === Arrange ===
        active = make_active_listing()
        make_active_listing(status=Listing.Status.DRAFT, published_at=None, ends_at=None)
        make_active_listing(status=Listing.Status.ENDED)
        make_active_listing(status=Listing.Status.CANCELLED)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual([r['id'] for r in response.json()['results']], [active.pk])

    def test_it_returns_ended_listings_with_status_filter(self):
        # === Arrange ===
        make_active_listing()
        ended = make_active_listing(status=Listing.Status.ENDED)

        # === Act ===
        response = self.client.get(self.url, {'status': 'ended'})

        # === Assert ===
        self.assertEqual([r['id'] for r in response.json()['results']], [ended.pk])

    def test_it_never_returns_drafts_or_cancelled_listings(self):
        # === Arrange ===
        make_active_listing(status=Listing.Status.DRAFT, published_at=None, ends_at=None)
        make_active_listing(status=Listing.Status.CANCELLED)

        for value in ('draft', 'cancelled'):
            with self.subTest(status=value):
                # === Act ===
                response = self.client.get(self.url, {'status': value})

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_returns_error_if_status_is_not_valid(self):
        # === Act ===
        response = self.client.get(self.url, {'status': 'bogus'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'status': 400,
                'errors': [
                    {
                        'param': 'status',
                        'message': 'Select a valid choice. bogus is not one of the available choices.',
                        'code': 'invalid_choice',
                    }
                ],
            },
        )

    def test_it_filters_by_category(self):
        # === Arrange ===
        books = Category.objects.get(slug='books')
        make_active_listing(category=self.category)
        in_books = make_active_listing(category=books)

        # === Act ===
        response = self.client.get(self.url, {'category': 'books'})

        # === Assert ===
        self.assertEqual([r['id'] for r in response.json()['results']], [in_books.pk])

    def test_it_returns_empty_list_for_unknown_category(self):
        # === Arrange ===
        make_active_listing()

        # === Act ===
        response = self.client.get(self.url, {'category': 'no-such-category'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['results'], [])

    def test_it_returns_newest_listings_first(self):
        # === Arrange ===
        now = timezone.now()
        old = make_active_listing(published_at=now - timedelta(hours=2))
        new = make_active_listing(published_at=now)
        middle = make_active_listing(published_at=now - timedelta(hours=1))

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual([r['id'] for r in response.json()['results']], [new.pk, middle.pk, old.pk])

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
