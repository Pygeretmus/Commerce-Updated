from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from listings.tests.helpers import make_active_listing

from ..models import Notification
from .helpers import note

User = get_user_model()


class APINotificationMarkReadViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = G(User)
        cls.other = G(User)
        cls.listing = make_active_listing(seller=None, title='Blue vase')

    def note(self, user, **kwargs) -> Notification:
        return Notification.objects.create(
            recipient=user, kind=kwargs.pop('kind', 'lost'), listing=self.listing, **kwargs
        )

    def test_it_marks_chosen_notifications_as_read(self):
        # === Arrange ===
        first, second = note(self.me, self.listing), note(self.me, self.listing)
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.post(reverse('notifications:notification-read'), {'ids': [first.pk]})

        # === Assert ===
        self.assertEqual(response.json(), {'updated': 1})
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNotNone(first.read_at)
        self.assertIsNone(second.read_at)

    def test_it_marks_everything_as_read(self):
        # === Arrange ===
        note(self.me, self.listing)
        note(self.me, self.listing)
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.post(reverse('notifications:notification-read'), {'all': True})

        # === Assert ===
        self.assertEqual(response.json(), {'updated': 2})
        self.assertFalse(Notification.objects.filter(read_at__isnull=True).exists())

    def test_it_ignores_other_peoples_notifications(self):
        # === Arrange ===
        theirs = note(self.other, self.listing)
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.post(reverse('notifications:notification-read'), {'ids': [theirs.pk]})

        # === Assert ===
        self.assertEqual(response.json(), {'updated': 0})
        theirs.refresh_from_db()
        self.assertIsNone(theirs.read_at)

    def test_it_needs_ids_or_all(self):
        # === Arrange ===
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.post(reverse('notifications:notification-read'), {})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.post(reverse('notifications:notification-read'), {})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
