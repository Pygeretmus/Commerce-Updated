from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from notifications.models import Notification

from ..models import Comment, Listing
from .helpers import make_active_listing, make_listing

User = get_user_model()


class APICommentCreateViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.alice = G(User, username='alice')

    def setUp(self):
        cache.clear()
        self.listing = make_active_listing(seller=self.seller)
        self.url = reverse('listings:comment-list', args=[self.listing.pk])

    def test_it_creates_a_comment(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.post(self.url, {'body': '  Is it signed?  '})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(
            (data['body'], data['author'], data['is_mine'], data['is_seller']), ('Is it signed?', 'alice', True, False)
        )
        self.assertEqual(Comment.objects.get().listing, self.listing)

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.post(self.url, {'body': 'Hi'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_rejects_empty_and_too_long_text(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        for body in ('', '   ', 'x' * 1001):
            with self.subTest(length=len(body)):
                # === Act ===
                response = self.client.post(self.url, {'body': body})

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()['errors'][0]['param'], 'body')
        self.assertEqual(Comment.objects.count(), 0)

    def test_it_marks_the_seller_and_works_on_ended_listings(self):
        # === Arrange ===
        ended = make_listing(seller=self.seller, status=Listing.Status.ENDED)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(reverse('listings:comment-list', args=[ended.pk]), {'body': 'Thanks, all'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()['is_seller'])

    def test_it_returns_not_found_for_a_draft(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.post(reverse('listings:comment-list', args=[draft.pk]), {'body': 'Hi'})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_notifies_the_seller_about_a_question(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        self.client.post(self.url, {'body': 'Is it signed?'})

        # === Assert ===
        note = Notification.objects.get()
        self.assertEqual(
            (note.recipient, note.kind, note.listing, note.data),
            (self.seller, 'new_comment', self.listing, {'author': 'alice'}),
        )

    def test_it_notifies_askers_about_the_answer_but_not_the_seller_herself(self):
        # === Arrange ===
        bob = G(User)
        Comment.objects.create(listing=self.listing, author=self.alice, body='Q1')
        Comment.objects.create(listing=self.listing, author=self.alice, body='Q1 again')
        Comment.objects.create(listing=self.listing, author=bob, body='Q2')
        self.client.force_authenticate(self.seller)

        # === Act ===
        self.client.post(self.url, {'body': 'Answer'})

        # === Assert === (one notification per person, none for the seller)
        self.assertCountEqual(Notification.objects.values_list('recipient', flat=True), [self.alice.pk, bob.pk])

    def test_it_throttles_comments(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'comment': '2/min'}):
            # === Act ===
            codes = [self.client.post(self.url, {'body': 'hi'}).status_code for _ in range(3)]

        # === Assert ===
        self.assertEqual(codes, [201, 201, 429])
