from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from ..services.tickets import consume_ticket

User = get_user_model()
URL_NAME = 'notifications:ws-ticket'


class APIWebSocketTicketViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.me = G(User)

    def setUp(self):
        self.addCleanup(cache.clear)

    def test_it_requires_a_login(self):
        # === Act ===
        response = self.client.post(reverse(URL_NAME))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_gives_a_ticket_that_belongs_to_the_caller(self):
        # === Arrange ===
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.post(reverse(URL_NAME))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['expires_in'], settings.TICKET_TTL)
        self.assertEqual(consume_ticket(response.data['ticket']), self.me.pk)

    def test_it_only_answers_post(self):
        # === Arrange ===
        self.client.force_authenticate(self.me)

        # === Act ===
        response = self.client.get(reverse(URL_NAME))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'ws_ticket': '3/min'})
    def test_it_counts_every_request_once_against_the_limit(self):
        # === Arrange ===
        self.client.force_authenticate(self.me)

        # === Act ===
        codes = [self.client.post(reverse(URL_NAME)).status_code for _ in range(5)]

        # === Assert === (a doubled throttle would let only one or two through)
        self.assertEqual(codes, [200, 200, 200, 429, 429])
