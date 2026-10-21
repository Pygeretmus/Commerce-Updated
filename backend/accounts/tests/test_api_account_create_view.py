from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

User = get_user_model()


class APIAccountCreateViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.request_data = {
            'username': 'JohnDoe',
            'email': 'john@example.com',
            'password': 'Sup3r-Str0ng-Pa55word',
        }

    def setUp(self):
        cache.clear()
        self.url = reverse('accounts:account-create')

    def test_it_creates_account(self):
        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get(email=self.request_data['email'])
        self.assertEqual(
            response.json(),
            {
                'id': user.pk,
                'username': 'JohnDoe',
                'email': 'john@example.com',
            },
        )

    def test_it_stores_emails_in_lower_case(self):
        # === Arrange ===
        self.request_data['email'] = 'JOHN@EXAMPLE.COM'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='john@example.com').exists())

    def test_it_hashes_password(self):
        # === Act ===
        self.client.post(self.url, data=self.request_data)

        # === Assert ===
        user = User.objects.get(email=self.request_data['email'])
        self.assertNotEqual(user.password, self.request_data['password'])
        self.assertTrue(user.check_password(self.request_data['password']))

    def test_it_returns_error_if_email_already_exists(self):
        # === Arrange ===
        G(User, email=self.request_data['email'])

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'errors': [
                    {
                        'param': 'email',
                        'message': 'user with this email already exists.',
                        'code': 'unique',
                    }
                ],
                'status': 400,
            },
        )
        self.assertEqual(User.objects.count(), 1)

    def test_it_returns_error_if_email_already_exists_in_different_case(self):
        # === Arrange ===
        G(User, email=self.request_data['email'])
        self.request_data['email'] = self.request_data['email'].upper()

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'errors': [
                    {
                        'param': 'email',
                        'message': 'user with this email already exists.',
                        'code': 'unique',
                    }
                ],
                'status': 400,
            },
        )

    def test_it_returns_error_if_email_is_not_valid(self):
        # === Arrange ===
        self.request_data['email'] = 'not-an-email'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'errors': [
                    {
                        'param': 'email',
                        'message': 'Enter a valid email address.',
                        'code': 'invalid',
                    }
                ],
                'status': 400,
            },
        )

    def test_it_returns_error_if_password_is_weak(self):
        # === Arrange ===
        self.request_data['password'] = '123'

        # === Act ===
        response = self.client.post(self.url, data=self.request_data)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'status': 400,
                'errors': [
                    {
                        'param': 'password',
                        'message': 'This password is too short. It must contain at least 8 characters.',
                        'code': 'password_too_short',
                    },
                    {'param': 'password', 'message': 'This password is too common.', 'code': 'password_too_common'},
                    {
                        'param': 'password',
                        'message': 'This password is entirely numeric.',
                        'code': 'password_entirely_numeric',
                    },
                ],
            },
        )

    def test_it_returns_error_if_required_field_missing(self):
        for field in ('email', 'password'):
            with self.subTest(field=field):
                # === Arrange ===
                data = self.request_data.pop(field)

                # === Act ===
                response = self.client.post(self.url, data=self.request_data)

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
                self.assertEqual(User.objects.count(), 0)
                self.request_data[field] = data

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'register': '2/min'})
    def test_it_returns_error_if_success_requests_too_frequent(self):

        # === Act ===
        for _ in range(3):
            self.request_data['email'] = self.request_data['email'] + '1'
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

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'register': '2/min'})
    def test_it_returns_error_if_error_requests_too_frequent(self):
        # === Arrange ===
        self.request_data['password'] = '123'

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
