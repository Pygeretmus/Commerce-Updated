from django.contrib.auth import get_user_model
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Comment, Listing
from .helpers import make_active_listing, make_listing

User = get_user_model()


class APICommentListViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.alice = G(User, username='alice')

    def setUp(self):
        self.listing = make_active_listing(seller=self.seller)
        self.url = reverse('listings:comment-list', args=[self.listing.pk])

    def test_it_lists_comments_oldest_first_and_marks_the_seller(self):
        # === Arrange ===
        question = Comment.objects.create(listing=self.listing, author=self.alice, body='Is it signed?')
        answer = Comment.objects.create(listing=self.listing, author=self.seller, body='Yes, on the back.')
        self.client.force_authenticate(self.alice)

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()['results']
        self.assertEqual([r['id'] for r in rows], [question.pk, answer.pk])
        self.assertEqual([r['is_seller'] for r in rows], [False, True])
        self.assertEqual([r['is_mine'] for r in rows], [True, False])
        self.assertEqual(rows[0]['author'], 'alice')

    def test_it_is_public(self):
        # === Arrange ===
        Comment.objects.create(listing=self.listing, author=self.alice, body='Hello')

        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()['results'][0]['is_mine'])

    def test_it_hides_deleted_comments(self):
        # === Arrange ===
        from django.utils import timezone

        Comment.objects.create(listing=self.listing, author=self.alice, body='Gone', deleted_at=timezone.now())
        Comment.objects.create(listing=self.listing, author=self.alice, body='Here')

        # === Act ===
        rows = self.client.get(self.url).json()['results']

        # === Assert ===
        self.assertEqual([r['body'] for r in rows], ['Here'])

    def test_it_shows_a_deleted_author_as_null(self):
        # === Arrange ===
        gone = G(User)
        Comment.objects.create(listing=self.listing, author=gone, body='Bye')
        gone.delete()

        # === Act ===
        row = self.client.get(self.url).json()['results'][0]

        # === Assert ===
        self.assertIsNone(row['author'])
        self.assertFalse(row['is_seller'])

    def test_it_uses_a_fixed_number_of_queries(self):
        # === Arrange ===
        for _ in range(10):
            Comment.objects.create(listing=self.listing, author=G(User), body='x')

        # === Act & Assert === (listing, count, comments with authors)
        with self.assertNumQueries(3):
            self.client.get(self.url)

    def test_it_returns_not_found_for_a_draft_even_to_its_seller(self):
        # === Arrange ===
        draft = make_listing(seller=self.seller, status=Listing.Status.DRAFT)
        self.client.force_authenticate(self.seller)

        # === Act ===
        response = self.client.get(reverse('listings:comment-list', args=[draft.pk]))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
