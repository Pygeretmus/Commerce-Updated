from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from ..models import Category, Listing
from ..services.drafts import MAX_DRAFTS
from .helpers import make_listing

User = get_user_model()


class APIListingCreateViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = G(User)
        cls.category = Category.objects.get(slug='art')

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('listings:listing-list')
        self.request_data = {
            'title': 'Old vase',
            'description': 'A vase from the last century.',
            'starting_price': '10.50',
            'reserve_price': '25.00',
            'category': self.category.pk,
        }

    def assert_single_error(self, response, param, code):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.json()['errors']
        self.assertEqual([(e['param'], e['code']) for e in errors], [(param, code)])
        self.assertEqual(Listing.objects.count(), 0)

    def test_it_creates_draft(self):
        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        listing = Listing.objects.get()
        self.assertEqual(listing.seller, self.user)
        self.assertEqual(listing.status, 'draft')
        self.assertEqual(listing.title, 'Old vase')
        self.assertEqual(listing.starting_price, Decimal('10.50'))
        self.assertEqual(listing.reserve_price, Decimal('25.00'))
        self.assertEqual(listing.category, self.category)
        self.assertIsNone(listing.published_at)
        self.assertIsNone(listing.ends_at)

    def test_it_returns_detail_with_reserve_to_the_seller(self):
        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        data = response.json()
        self.assertEqual(data['id'], Listing.objects.get().pk)
        self.assertEqual(data['seller'], self.user.username)
        self.assertEqual(data['status'], 'draft')
        self.assertEqual(data['reserve_price'], '25.00')
        self.assertTrue(data['has_reserve'])
        self.assertEqual(data['images'], [])

    def test_it_creates_draft_without_reserve_price(self):
        # === Arrange ===
        del self.request_data['reserve_price']

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(Listing.objects.get().reserve_price)
        self.assertFalse(response.json()['has_reserve'])

    def test_it_strips_whitespace_from_title(self):
        # === Arrange ===
        self.request_data['title'] = '   Old vase  '

        # === Act ===
        self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(Listing.objects.get().title, 'Old vase')

    def test_it_ignores_status_and_seller_sent_by_client(self):
        # === Arrange ===
        other = G(User)
        self.request_data.update({'status': 'active', 'seller': other.pk, 'ends_at': '2030-01-01T00:00:00Z'})

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        listing = Listing.objects.get()
        self.assertEqual(listing.status, 'draft')
        self.assertEqual(listing.seller, self.user)
        self.assertIsNone(listing.ends_at)

    def test_it_returns_error_if_required_field_missing(self):
        for field in ('title', 'description', 'starting_price', 'category'):
            with self.subTest(field=field):
                # === Arrange ===
                data = {k: v for k, v in self.request_data.items() if k != field}

                # === Act ===
                response = self.client.post(self.url, data=data)

                # === Assert ===
                self.assert_single_error(response, field, 'required')

    def test_it_returns_error_if_title_is_too_short(self):
        # === Arrange ===
        self.request_data['title'] = 'ab'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'title', 'min_length')

    def test_it_returns_error_if_title_is_too_short_after_stripping(self):
        # === Arrange ===
        self.request_data['title'] = '  ab  '

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'title', 'min_length')

    def test_it_returns_error_if_title_is_too_long(self):
        # === Arrange ===
        self.request_data['title'] = 'a' * 121

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'title', 'max_length')

    def test_it_returns_error_if_title_is_only_spaces(self):
        # === Arrange ===
        self.request_data['title'] = '     '

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'title', 'blank')

    def test_it_returns_error_if_description_is_only_spaces(self):
        # === Arrange ===
        self.request_data['description'] = '   '

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'description', 'blank')

    def test_it_returns_error_if_description_is_too_long(self):
        # === Arrange ===
        self.request_data['description'] = 'a' * 5001

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'description', 'max_length')

    def test_it_returns_error_if_starting_price_is_not_positive(self):
        for value in ('0', '0.00', '-1'):
            with self.subTest(value=value):
                # === Arrange ===
                self.request_data['starting_price'] = value
                self.request_data['reserve_price'] = None

                # === Act ===
                response = self.client.post(self.url, data=self.request_data)

                # === Assert ===
                self.assert_single_error(response, 'starting_price', 'min_value')

    def test_it_returns_error_if_starting_price_has_too_many_decimal_places(self):
        # === Arrange ===
        self.request_data['starting_price'] = '10.505'
        self.request_data['reserve_price'] = None

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'starting_price', 'max_decimal_places')

    def test_it_returns_error_if_starting_price_is_too_big(self):
        # === Arrange ===
        self.request_data['starting_price'] = '100000000000.00'
        self.request_data['reserve_price'] = None

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'starting_price', 'max_digits')

    def test_it_returns_error_if_reserve_price_is_below_starting_price(self):
        # === Arrange ===
        self.request_data['reserve_price'] = '10.49'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'reserve_price', 'reserve_below_starting_price')

    def test_it_allows_reserve_price_equal_to_starting_price(self):
        # === Arrange ===
        self.request_data['reserve_price'] = '10.50'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_it_returns_error_if_category_does_not_exist(self):
        # === Arrange ===
        self.request_data['category'] = 999999

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assert_single_error(response, 'category', 'does_not_exist')

    def test_it_returns_error_if_draft_limit_reached(self):
        # === Arrange ===
        for _ in range(MAX_DRAFTS):
            make_listing(seller=self.user)

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'draft_limit')
        self.assertEqual(Listing.objects.count(), MAX_DRAFTS)

    def test_it_does_not_count_other_sellers_or_published_listings_in_draft_limit(self):
        # === Arrange ===
        for _ in range(MAX_DRAFTS):
            make_listing(seller=G(User))
        for _ in range(3):
            make_listing(seller=self.user, status=Listing.Status.CANCELLED)

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Listing.objects.count(), 0)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'listing_write': '2/min'})
    def test_it_returns_error_if_requests_too_frequent(self):
        # === Act ===
        for _ in range(3):
            response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(Listing.objects.count(), 2)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'listing_write': '1/min'})
    def test_it_does_not_throttle_reading_the_list(self):
        # === Act ===
        responses = [self.client.get(self.url) for _ in range(3)]

        # === Assert ===
        self.assertEqual({r.status_code for r in responses}, {status.HTTP_200_OK})
