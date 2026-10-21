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
from .helpers import make_active_listing, make_listing

User = get_user_model()


class APIListingUpdateViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.seller)
        self.listing = make_listing(
            seller=self.seller, title='Old vase', starting_price=Decimal(10), reserve_price=Decimal(20)
        )
        self.url = reverse('listings:listing-detail', args=[self.listing.pk])

    def test_it_partially_updates_draft(self):
        # === Arrange ===
        data = {'title': 'New title', 'description': 'New description'}

        # === Act ===
        response = self.client.patch(self.url, data=data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'New title')
        self.assertEqual(self.listing.description, 'New description')
        self.assertEqual(self.listing.starting_price, Decimal(10))
        self.assertEqual(response.json()['title'], 'New title')
        self.assertEqual(response.json()['reserve_price'], '20.00')

    def test_it_updates_category(self):
        # === Arrange ===
        books = Category.objects.get(slug='books')

        # === Act ===
        response = self.client.patch(self.url, data={'category': books.pk})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.category, books)

    def test_it_refreshes_updated_at(self):
        # === Arrange ===
        before = self.listing.updated_at

        # === Act ===
        self.client.patch(self.url, data={'title': 'New title'})

        # === Assert ===
        self.listing.refresh_from_db()
        self.assertGreater(self.listing.updated_at, before)

    def test_it_removes_reserve_price_with_null(self):
        # === Act ===
        response = self.client.patch(self.url, data={'reserve_price': None})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertIsNone(self.listing.reserve_price)

    def test_it_ignores_status_and_seller_sent_by_client(self):
        # === Act ===
        response = self.client.patch(self.url, data={'status': 'active', 'seller': self.other.pk, 'title': 'New title'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'draft')
        self.assertEqual(self.listing.seller, self.seller)

    def test_it_returns_error_if_title_is_too_short(self):
        # === Act ===
        response = self.client.patch(self.url, data={'title': 'ab'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['param'], 'title')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'Old vase')

    def test_it_compares_new_reserve_price_with_stored_starting_price(self):
        # === Act === (stored starting price is 10)
        response = self.client.patch(self.url, data={'reserve_price': '9.99'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'reserve_below_starting_price')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.reserve_price, Decimal(20))

    def test_it_compares_new_starting_price_with_stored_reserve_price(self):
        # === Act === (stored reserve price is 20)
        response = self.client.patch(self.url, data={'starting_price': '20.01'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'reserve_below_starting_price')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.starting_price, Decimal(10))

    def test_it_allows_changing_both_prices_at_once(self):
        # === Act ===
        response = self.client.patch(self.url, data={'starting_price': '30', 'reserve_price': '40'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual((self.listing.starting_price, self.listing.reserve_price), (Decimal(30), Decimal(40)))

    def test_it_allows_raising_starting_price_when_there_is_no_reserve(self):
        # === Arrange ===
        self.listing.reserve_price = None
        self.listing.save()

        # === Act ===
        response = self.client.patch(self.url, data={'starting_price': '500'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_it_returns_forbidden_for_other_users_published_listing(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.other, title='Vase')
        url = reverse('listings:listing-detail', args=[listing.pk])

        # === Act ===
        response = self.client.patch(url, data={'title': 'Hacked'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        listing.refresh_from_db()
        self.assertEqual(listing.title, 'Vase')

    def test_it_returns_not_found_for_other_users_draft(self):
        # === Arrange ===
        listing = make_listing(seller=self.other, title='Vase')
        url = reverse('listings:listing-detail', args=[listing.pk])

        # === Act ===
        response = self.client.patch(url, data={'title': 'Hacked'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        listing.refresh_from_db()
        self.assertEqual(listing.title, 'Vase')

    def test_it_returns_conflict_if_listing_is_not_a_draft(self):
        for value in (Listing.Status.ACTIVE, Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=value):
                # === Arrange ===
                listing = make_active_listing(seller=self.seller, status=value, title='Vase')
                url = reverse('listings:listing-detail', args=[listing.pk])

                # === Act ===
                response = self.client.patch(url, data={'title': 'Changed'})

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                self.assertEqual(
                    response.json(),
                    {
                        'status': 409,
                        'errors': [
                            {
                                'param': None,
                                'message': 'Only a draft can be changed or deleted.',
                                'code': 'not_editable',
                            }
                        ],
                    },
                )
                listing.refresh_from_db()
                self.assertEqual(listing.title, 'Vase')

    def test_it_does_not_allow_put(self):
        # === Act ===
        response = self.client.put(self.url, data={'title': 'New title'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.patch(self.url, data={'title': 'New title'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'Old vase')

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'listing_write': '2/min'})
    def test_it_returns_error_if_requests_too_frequent(self):
        # === Act ===
        for _ in range(3):
            response = self.client.patch(self.url, data={'title': 'New title'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
