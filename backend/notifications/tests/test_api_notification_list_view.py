from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from listings.tests.helpers import make_active_listing

from .helpers import note

User = get_user_model()


class APINotificationListViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = G(User)
        cls.other = G(User)
        cls.listing = make_active_listing(seller=None, title='Blue vase')

    def test_it_lists_my_notifications_newest_first(self):
        # === Arrange ===
        first, second = (
            note(self.me, self.listing),
            note(self.me, self.listing, kind='outbid', data={'amount': '12.00'}),
        )
        note(self.other, self.listing)
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.get(reverse('notifications:notification-list'))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()['results']
        self.assertEqual([r['id'] for r in rows], [second.pk, first.pk])
        self.assertEqual(rows[0]['text'], 'You were outbid on "Blue vase". The price is now $12.00.')
        self.assertEqual(rows[0]['listing'], {'id': self.listing.pk, 'title': 'Blue vase'})
        self.assertIsNone(rows[0]['read_at'])

    def test_it_filters_unread(self):
        # === Arrange ===
        from django.utils import timezone

        note(self.me, self.listing, read_at=timezone.now())
        unread = note(self.me, self.listing)
        self.client.force_authenticate(self.me)

        # === Act ===
        rows = self.client.get(reverse('notifications:notification-list') + '?unread=true').json()['results']

        # === Assert ===
        self.assertEqual([r['id'] for r in rows], [unread.pk])

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.get(reverse('notifications:notification-list'))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_uses_a_fixed_number_of_queries(self):
        # === Arrange ===
        for _ in range(10):
            note(self.me, self.listing)
        self.client.force_authenticate(self.me)

        # === Act & Assert === (count and rows with their listings)
        with self.assertNumQueries(2):
            self.client.get(reverse('notifications:notification-list'))
