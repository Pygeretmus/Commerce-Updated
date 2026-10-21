from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Category, Listing, ListingImage
from .helpers import make_active_listing, make_listing, make_listing_image

User = get_user_model()


class APIListingDestroyViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.seller)
        self.listing = make_listing(seller=self.seller)
        self.url = reverse('listings:listing-detail', args=[self.listing.pk])

    def test_it_deletes_draft(self):
        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())

    def test_it_deletes_images_of_the_draft(self):
        # === Arrange ===
        ListingImage.objects.create(listing=self.listing, image='listings/a.jpg')

        # === Act ===
        self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(ListingImage.objects.count(), 0)

    def test_it_deletes_files_of_the_draft_from_storage_after_commit(self):
        # === Arrange ===
        names = [make_listing_image(self.listing, position).image.name for position in range(2)]
        self.assertTrue(all(default_storage.exists(name) for name in names))

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(self.url)

        # === Assert ===
        self.assertFalse(any(default_storage.exists(name) for name in names))

    def test_it_deletes_thumbnail_files_of_the_draft_too(self):
        # === Arrange ===
        photo = make_listing_image(self.listing)
        photo.thumbnail.save('thumbs/t.webp', ContentFile(b'thumb'), save=True)
        names = [photo.image.name, photo.thumbnail.name]

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(self.url)

        # === Assert ===
        self.assertFalse(any(default_storage.exists(name) for name in names))

    def test_it_keeps_files_if_the_listing_is_not_deleted(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        name = make_listing_image(listing).image.name

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(reverse('listings:listing-detail', args=[listing.pk]))

        # === Assert ===
        self.assertTrue(default_storage.exists(name))

    def test_it_keeps_category(self):
        # === Act ===
        self.client.delete(self.url)

        # === Assert ===
        self.assertTrue(Category.objects.filter(slug='art').exists())

    def test_it_returns_forbidden_for_other_users_published_listing(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.other)
        url = reverse('listings:listing-detail', args=[listing.pk])

        # === Act ===
        response = self.client.delete(url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Listing.objects.filter(pk=listing.pk).exists())

    def test_it_returns_not_found_for_other_users_draft(self):
        # === Arrange ===
        listing = make_listing(seller=self.other)
        url = reverse('listings:listing-detail', args=[listing.pk])

        # === Act ===
        response = self.client.delete(url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Listing.objects.filter(pk=listing.pk).exists())

    def test_it_returns_conflict_if_listing_is_not_a_draft(self):
        for value in (Listing.Status.ACTIVE, Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=value):
                # === Arrange ===
                listing = make_active_listing(seller=self.seller, status=value)
                url = reverse('listings:listing-detail', args=[listing.pk])

                # === Act ===
                response = self.client.delete(url)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                self.assertTrue(Listing.objects.filter(pk=listing.pk).exists())

    def test_it_returns_not_found_when_deleted_twice(self):
        # === Arrange ===
        self.client.delete(self.url)

        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
