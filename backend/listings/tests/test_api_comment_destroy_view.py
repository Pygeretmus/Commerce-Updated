from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Comment
from .helpers import make_active_listing

User = get_user_model()


class APICommentDestroyViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.alice = G(User)
        cls.bob = G(User)

    def setUp(self):
        self.listing = make_active_listing(seller=self.seller)
        self.comment = Comment.objects.create(listing=self.listing, author=self.alice, body='Hi')
        self.url = reverse('listings:comment-detail', args=[self.comment.pk])

    def test_it_hides_my_comment_without_erasing_it(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.comment.refresh_from_db()
        self.assertIsNotNone(self.comment.deleted_at)

    def test_it_requires_authentication(self):
        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_forbids_deleting_somebody_elses_comment_even_for_the_seller(self):
        for user in (self.bob, self.seller):
            with self.subTest(user=user.pk):
                # === Arrange ===
                self.client.force_authenticate(user)

                # === Act ===
                response = self.client.delete(self.url)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.comment.refresh_from_db()
        self.assertIsNone(self.comment.deleted_at)

    def test_it_returns_not_found_for_a_deleted_or_unknown_comment(self):
        # === Arrange ===
        self.client.force_authenticate(self.alice)
        self.client.delete(self.url)

        # === Act ===
        again = self.client.delete(self.url)
        unknown = self.client.delete(reverse('listings:comment-detail', args=[999999]))

        # === Assert ===
        self.assertEqual((again.status_code, unknown.status_code), (404, 404))
