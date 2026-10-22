from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from listings.models import ListingImage
from listings.tests.helpers import make_active_listing, make_listing, make_listing_image

User = get_user_model()


class APIListingImageDestroyViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.seller)
        self.listing = make_listing(seller=self.seller)
        self.photo = make_listing_image(self.listing)
        self.url = self.url_for(self.listing, self.photo)

    def url_for(self, listing, photo) -> str:
        return reverse('listings:listing-image-detail', args=[listing.pk, photo.pk])

    def test_it_deletes_photo(self):
        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ListingImage.objects.filter(pk=self.photo.pk).exists())

    def test_it_deletes_the_file_from_storage_after_commit(self):
        # === Arrange ===
        name = self.photo.image.name
        self.assertTrue(default_storage.exists(name))

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(self.url)

        # === Assert ===
        self.assertFalse(default_storage.exists(name))

    def test_it_deletes_the_thumbnail_file_too(self):
        # === Arrange ===
        self.photo.thumbnail.save('thumbs/t.webp', ContentFile(b'thumb'), save=True)
        names = [self.photo.image.name, self.photo.thumbnail.name]
        self.assertTrue(all(default_storage.exists(name) for name in names))

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(self.url)

        # === Assert ===
        self.assertFalse(any(default_storage.exists(name) for name in names))

    def test_it_keeps_the_other_photos(self):
        # === Arrange ===
        other_photo = make_listing_image(self.listing, position=1)

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(self.url)

        # === Assert ===
        self.assertTrue(ListingImage.objects.filter(pk=other_photo.pk).exists())
        self.assertTrue(default_storage.exists(other_photo.image.name))

    def test_it_returns_not_found_for_photo_of_another_listing(self):
        # === Arrange ===
        another = make_listing(seller=self.seller)
        photo = make_listing_image(another)

        # === Act === (the photo exists, but not in this listing)
        response = self.client.delete(self.url_for(self.listing, photo))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ListingImage.objects.filter(pk=photo.pk).exists())

    def test_it_returns_not_found_for_unknown_photo(self):
        # === Act ===
        response = self.client.delete(reverse('listings:listing-image-detail', args=[self.listing.pk, 999999]))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_conflict_if_listing_is_not_a_draft(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        photo = make_listing_image(listing)

        # === Act ===
        response = self.client.delete(self.url_for(listing, photo))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(ListingImage.objects.filter(pk=photo.pk).exists())

    def test_it_returns_forbidden_for_other_users_published_listing(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.other)
        photo = make_listing_image(listing)

        # === Act ===
        response = self.client.delete(self.url_for(listing, photo))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ListingImage.objects.filter(pk=photo.pk).exists())

    def test_it_returns_not_found_for_other_users_draft(self):
        # === Arrange ===
        listing = make_listing(seller=self.other)
        photo = make_listing_image(listing)

        # === Act ===
        response = self.client.delete(self.url_for(listing, photo))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ListingImage.objects.filter(pk=photo.pk).exists())

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.delete(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(ListingImage.objects.filter(pk=self.photo.pk).exists())
