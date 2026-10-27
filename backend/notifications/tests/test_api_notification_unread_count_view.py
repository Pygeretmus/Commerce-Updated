from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from listings.tests.helpers import make_active_listing

from ..models import Notification
from .helpers import note

User = get_user_model()


class APINotificationUnreadCountViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = G(User)
        cls.other = G(User)
        cls.listing = make_active_listing(seller=None, title='Blue vase')

    def note(self, user, **kwargs) -> Notification:
        return Notification.objects.create(
            recipient=user, kind=kwargs.pop('kind', 'lost'), listing=self.listing, **kwargs
        )

    def test_it_counts_my_unread_notifications_only(self):
        # === Arrange ===
        from django.utils import timezone

        note(self.me, self.listing)
        note(self.me, self.listing)
        note(self.me, self.listing, read_at=timezone.now())
        note(self.other, self.listing)
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.get(reverse('notifications:notification-unread-count'))

        # === Assert ===
        self.assertEqual(response.json(), {'count': 2})

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.get(reverse('notifications:notification-unread-count'))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
