from django.test import TestCase

from ..models import Category


class SeedCategoriesTest(TestCase):
    def test_it_seeds_categories_with_unique_slugs(self):
        self.assertGreaterEqual(Category.objects.count(), 10)
        self.assertEqual(Category.objects.values('slug').distinct().count(), Category.objects.count())
