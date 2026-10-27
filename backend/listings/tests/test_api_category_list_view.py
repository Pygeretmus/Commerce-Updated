from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Category


class APICategoryListViewTest(APITestCase):
    def setUp(self):

        self.url = reverse('listings:category-list')

    def test_it_returns_all_categories_to_anonymous_user(self):
        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), Category.objects.count())
        art = Category.objects.get(slug='art')
        self.assertIn({'id': art.pk, 'name': 'Art', 'slug': 'art'}, data)

    def test_it_returns_categories_sorted_by_name(self):
        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        names = [c['name'] for c in response.json()]
        self.assertEqual(names, sorted(names))
