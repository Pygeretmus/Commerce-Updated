from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

User = get_user_model()


class APIAccountPasswordChangeViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Sup3r-Str0ng-Pa55word'
        cls.new_password = 'An0ther-Str0ng-Pa55word'
        cls.user = User.objects.create_user(username='John Doe', email='john@example.com', password=cls.password)
        cls.request_data = {
            'current_password': cls.password,
            'new_password': cls.new_password,
        }

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:account-password')

    def test_it_changes_password(self):
        # === Act ===
        response = self.client.put(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'detail': 'Password successfully changed'})
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.password))
        self.assertTrue(self.user.check_password(self.new_password))

    def test_it_hashes_new_password(self):
        # === Act ===
        self.client.put(self.url, data=self.request_data)

        # === Assert ===
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.password, self.new_password)

    def test_it_returns_error_if_current_password_is_incorrect(self):
        # === Arrange ===
        self.request_data['current_password'] = 'wrong-password'

        # === Act ===
        response = self.client.put(self.url, data=self.request_data)

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
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_it_returns_error_if_required_field_missing(self):
        for field in ('current_password', 'new_password'):
            with self.subTest(field=field):
                # === Arrange ===
                data = self.request_data.pop(field)

                # === Act ===
                response = self.client.put(self.url, data=self.request_data)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(
                    response.json(),
                    {
                        'errors': [
                            {
                                'param': field,
                                'message': 'This field is required.',
                                'code': 'required',
                            }
                        ],
                        'status': 400,
                    },
                )
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(self.password))
                self.request_data[field] = data

    def test_it_returns_error_if_new_password_is_weak(self):
        # === Arrange ===
        self.request_data['new_password'] = '123'

        # === Act ===
        response = self.client.put(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'status': 400,
                'errors': [
                    {
                        'param': 'new_password',
                        'message': 'This password is too short. It must contain at least 8 characters.',
                        'code': 'password_too_short',
                    },
                    {'param': 'new_password', 'message': 'This password is too common.', 'code': 'password_too_common'},
                    {
                        'param': 'new_password',
                        'message': 'This password is entirely numeric.',
                        'code': 'password_entirely_numeric',
                    },
                ],
            },
        )

    def test_it_returns_validation_error_before_checking_current_password(self):
        # === Arrange ===
        self.request_data.update({'current_password': 'wrong-password', 'new_password': '123'})

        # === Act ===
        response = self.client.put(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'status': 400,
                'errors': [
                    {
                        'param': 'new_password',
                        'message': 'This password is too short. It must contain at least 8 characters.',
                        'code': 'password_too_short',
                    },
                    {'param': 'new_password', 'message': 'This password is too common.', 'code': 'password_too_common'},
                    {
                        'param': 'new_password',
                        'message': 'This password is entirely numeric.',
                        'code': 'password_entirely_numeric',
                    },
                ],
            },
        )

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.put(self.url, data=self.request_data)

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
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'password_check': '2/min'})
    def test_it_returns_error_if_success_requests_too_frequent(self):
        # === Act ===
        for _ in range(3):
            response = self.client.put(self.url, data=self.request_data)

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

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'password_check': '2/min'})
    def test_it_returns_error_if_error_requests_too_frequent(self):
        # === Arrange ===
        self.request_data['new_password'] = '123'

        # === Act ===
        for _ in range(3):
            response = self.client.post(self.url, data=self.request_data)

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
