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
