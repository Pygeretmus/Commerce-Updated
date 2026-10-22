from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django_dynamic_fixture import G
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from listings.models import Listing, ListingImage
from listings.tests.helpers import make_active_listing, make_image_file, make_listing, make_listing_image

User = get_user_model()


class APIListingImageCreateViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.seller)
        self.listing = make_listing(seller=self.seller)
        self.url = reverse('listings:listing-image-list', args=[self.listing.pk])

    def upload(self, file, url=None):
        return self.client.post(url or self.url, data={'image': file}, format='multipart')

    def stored_image(self, photo: ListingImage) -> Image.Image:
        with default_storage.open(photo.image.name) as stored:
            image = Image.open(BytesIO(stored.read()))
        image.load()
        return image

    def assert_error(self, response, code):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.json()['errors']
        self.assertEqual([(e['param'], e['code']) for e in errors], [('image', code)])
        self.assertEqual(ListingImage.objects.count(), 0)

    def test_it_uploads_photo(self):
        # === Act ===
        response = self.upload(make_image_file())

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        photo = ListingImage.objects.get()
        self.assertEqual(photo.listing, self.listing)
        self.assertEqual(
            response.json(),
            {'id': photo.pk, 'url': f'http://testserver/media/{photo.image.name}', 'thumbnail': None, 'position': 0},
        )
        self.assertTrue(default_storage.exists(photo.image.name))

    def test_it_accepts_jpeg_png_and_webp(self):
        for image_format, extension in (('JPEG', 'jpg'), ('PNG', 'png'), ('WEBP', 'webp')):
            with self.subTest(image_format=image_format):
                # === Act ===
                response = self.upload(make_image_file(image_format))

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                photo = ListingImage.objects.get(pk=response.json()['id'])
                self.assertTrue(photo.image.name.endswith(f'.{extension}'))
                self.assertEqual(self.stored_image(photo).format, image_format)

    def test_it_puts_photos_in_order_of_upload(self):
        # === Act ===
        positions = [self.upload(make_image_file()).json()['position'] for _ in range(3)]

        # === Assert ===
        self.assertEqual(positions, [0, 1, 2])

    def test_it_continues_after_the_last_position(self):
        # === Arrange ===
        make_listing_image(self.listing, position=5)

        # === Act ===
        response = self.upload(make_image_file())

        # === Assert ===
        self.assertEqual(response.json()['position'], 6)

    def test_it_ignores_the_file_name_sent_by_client(self):
        # === Arrange ===
        original = make_image_file(name='../../evil.php.jpg')

        # === Act ===
        response = self.upload(original)

        # === Assert ===
        photo = ListingImage.objects.get(pk=response.json()['id'])
        self.assertRegex(photo.image.name, rf'^listings/{self.listing.pk}/[0-9a-f]{{32}}\.jpg$')

    def test_it_returns_error_if_file_is_not_an_image(self):
        # === Arrange ===
        fake = SimpleUploadedFile('photo.jpg', b'<?php echo 1; ?>', 'image/jpeg')

        # === Act ===
        response = self.upload(fake)

        # === Assert ===
        self.assert_error(response, 'invalid_image')

    def test_it_returns_error_if_image_is_truncated(self):
        # === Arrange ===
        data = make_image_file().read()
        truncated = SimpleUploadedFile('photo.jpg', data[: len(data) // 2], 'image/jpeg')

        # === Act ===
        response = self.upload(truncated)

        # === Assert ===
        self.assert_error(response, 'invalid_image')

    def test_it_returns_error_if_format_is_not_supported(self):
        # === Act ===
        response = self.upload(make_image_file('GIF'))

        # === Assert ===
        self.assert_error(response, 'unsupported_format')

    @override_settings(IMAGE_MAX_BYTES=1000)
    def test_it_returns_error_if_file_is_too_large(self):
        # === Arrange ===
        noisy = SimpleUploadedFile('photo.jpg', make_image_file().read() + b'0' * 1000, 'image/jpeg')

        # === Act ===
        response = self.upload(noisy)

        # === Assert ===
        self.assert_error(response, 'file_too_large')

    def test_it_returns_error_if_image_is_too_small(self):
        # === Act ===
        response = self.upload(make_image_file(size=(199, 400)))

        # === Assert ===
        self.assert_error(response, 'dimensions_too_small')

    def test_it_returns_error_if_image_is_too_big_in_pixels(self):
        # === Act ===
        response = self.upload(make_image_file('PNG', size=(6001, 200)))

        # === Assert ===
        self.assert_error(response, 'dimensions_too_large')

    def test_it_returns_error_if_file_is_empty(self):
        # === Act ===
        response = self.upload(SimpleUploadedFile('photo.jpg', b'', 'image/jpeg'))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ListingImage.objects.count(), 0)

    def test_it_returns_error_if_file_is_missing(self):
        # === Act ===
        response = self.client.post(self.url, data={}, format='multipart')

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'status': 400, 'errors': [{'param': 'image', 'message': 'No file was submitted.', 'code': 'required'}]},
        )

    def test_it_returns_error_if_listing_has_too_many_photos(self):
        # === Arrange ===
        for position in range(8):
            make_listing_image(self.listing, position)

        # === Act ===
        response = self.upload(make_image_file())

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'image_limit')
        self.assertEqual(ListingImage.objects.count(), 8)

    def test_it_counts_only_photos_of_this_listing_in_the_limit(self):
        # === Arrange ===
        another = make_listing(seller=self.seller)
        for position in range(8):
            make_listing_image(another, position)

        # === Act ===
        response = self.upload(make_image_file())

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_it_returns_conflict_if_listing_is_not_a_draft(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)
        url = reverse('listings:listing-image-list', args=[listing.pk])

        # === Act ===
        response = self.upload(make_image_file(), url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ListingImage.objects.count(), 0)

    def test_it_returns_forbidden_for_other_users_published_listing(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.other)
        url = reverse('listings:listing-image-list', args=[listing.pk])

        # === Act ===
        response = self.upload(make_image_file(), url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ListingImage.objects.count(), 0)

    def test_it_returns_not_found_for_other_users_draft(self):
        # === Arrange ===
        listing = make_listing(seller=self.other)
        url = reverse('listings:listing-image-list', args=[listing.pk])

        # === Act ===
        response = self.upload(make_image_file(), url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_not_found_for_unknown_listing(self):
        # === Act ===
        response = self.upload(make_image_file(), reverse('listings:listing-image-list', args=[999999]))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.upload(make_image_file())

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(ListingImage.objects.count(), 0)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'image_upload': '2/min'})
    def test_it_returns_error_if_requests_too_frequent(self):
        # === Act ===
        for _ in range(3):
            response = self.upload(make_image_file())

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(ListingImage.objects.count(), 2)

    def test_it_does_not_change_the_listing(self):
        # === Arrange ===
        before = Listing.objects.values().get(pk=self.listing.pk)

        # === Act ===
        self.upload(make_image_file())

        # === Assert ===
        after = Listing.objects.values().get(pk=self.listing.pk)
        self.assertEqual(before, after)
