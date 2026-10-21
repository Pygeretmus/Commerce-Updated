from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class APIAccountRetrieveViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = G(User)

    def setUp(self):
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:account-me')

    def test_it_returns_current_user(self):
        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                'id': self.user.pk,
                'username': self.user.username,
                'email': self.user.email,
            },
        )

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.get(self.url)

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
