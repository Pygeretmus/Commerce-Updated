from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

User = get_user_model()


class APIAccountDestroyViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.request_data = {'current_password': 'secret_password'}
        cls.user = User.objects.create_user(
            username='John Doe', email='john@example.com', password=cls.request_data['current_password']
        )

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:account-destroy')

    def test_it_destroys_account(self):
        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_it_returns_error_if_current_password_is_incorrect(self):
        # === Arrange ===
        self.request_data['current_password'] = 'wrong-password'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'errors': [
                    {
                        'param': 'current_password',
                        'message': 'Incorrect current password',
                        'code': 'invalid',
                    }
                ],
                'status': 400,
            },
        )
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_it_returns_error_if_current_password_missing(self):
        # === Act ===
        response = self.client.post(self.url, data={})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'errors': [
                    {
                        'param': 'current_password',
                        'message': 'This field is required.',
                        'code': 'required',
                    }
                ],
                'status': 400,
            },
        )
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json(),
            {
                'errors': [
                    {
                        'param': None,
                        'message': 'Authentication credentials were not provided.',
                        'code': 'not_authenticated',
                    }
                ],
                'status': 401,
            },
        )

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'password_check': '2/min'})
    def test_it_returns_error_if_error_requests_too_frequent(self):
        # === Act ===
        for _ in range(3):
            response = self.client.post(self.url, data={})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            response.json(),
            {
                'status': 429,
                'errors': [
                    {
                        'param': None,
                        'message': 'Request was throttled. Expected available in 60 seconds.',
                        'code': 'throttled',
                    }
                ],
            },
        )


class APIAccountDestroyGuardTest(APITestCase):
    """An account with unfinished business cannot be deleted; afterwards the person becomes "Deleted user"."""

    @classmethod
    def setUpTestData(cls):
        cls.password = 'secret_password'
        cls.user = User.objects.create_user(username='leaving', email='leaving@example.com', password=cls.password)
        cls.seller = User.objects.create_user(username='shop', email='shop@example.com', password=cls.password)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:account-destroy')

    def destroy(self):
        return self.client.post(self.url, data={'current_password': self.password})

    def test_it_refuses_while_the_user_has_an_active_listing(self):
        # === Arrange ===
        from listings.tests.helpers import make_active_listing

        make_active_listing(seller=self.user)

        # === Act ===
        response = self.destroy()

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'has_active_listings')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_it_refuses_while_the_user_is_the_top_bidder_of_an_active_auction(self):
        # === Arrange ===
        from listings.tests.helpers import bid_on, make_active_listing

        listing = make_active_listing(seller=self.seller)
        bid_on(listing, self.user, listing.starting_price)

        # === Act ===
        response = self.destroy()

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'is_top_bidder')

    def test_it_allows_deleting_once_the_user_is_outbid(self):
        # === Arrange ===
        from listings.models import Listing
        from listings.tests.helpers import bid_on, make_active_listing

        listing = make_active_listing(seller=self.seller)
        bid_on(listing, self.user, listing.starting_price)
        rival = User.objects.create_user(username='rival', email='rival@example.com', password=self.password)
        bid_on(listing, rival, '100.00')

        # === Act ===
        response = self.destroy()

        # === Assert === (the old bid stays in the history, without a name)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(listing.bids.filter(bidder__isnull=True).exists())
        self.assertEqual(Listing.objects.get(pk=listing.pk).bids_count, 2)

    def test_it_allows_deleting_after_the_auctions_have_ended(self):
        # === Arrange ===
        from listings.models import Listing
        from listings.tests.helpers import make_listing

        listing = make_listing(seller=self.user, status=Listing.Status.ENDED)

        # === Act ===
        response = self.destroy()

        # === Assert === (the finished lot stays, without a seller)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(Listing.objects.get(pk=listing.pk).seller)

    def test_it_deletes_the_drafts_of_the_user_together_with_the_account(self):
        # === Arrange ===
        from listings.models import Listing
        from listings.tests.helpers import make_listing

        make_listing(seller=self.user, status=Listing.Status.DRAFT)

        # === Act ===
        response = self.destroy()

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Listing.objects.count(), 0)
