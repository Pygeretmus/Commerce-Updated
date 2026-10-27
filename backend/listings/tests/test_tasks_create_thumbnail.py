from io import BytesIO

from django.core.files.storage import default_storage
from django.test import TestCase
from PIL import Image

from ..models import ListingImage
from ..tasks import create_thumbnail
from .helpers import make_image_file, make_listing


class CreateThumbnailTaskTest(TestCase):
    def setUp(self):
        self.listing = make_listing()

    def make_photo(self, **image_options) -> ListingImage:
        photo = ListingImage(listing=self.listing)
        photo.image.save('original.img', make_image_file(**image_options), save=False)
        photo.save()
        return photo

    def stored(self, name: str) -> Image.Image:
        with default_storage.open(name) as file:
            return Image.open(BytesIO(file.read()))

    def test_it_creates_webp_thumbnail_with_longer_side_of_400(self):
        # === Arrange ===
        photo = self.make_photo(size=(1000, 500))

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        thumbnail = self.stored(photo.thumbnail.name)
        self.assertEqual(thumbnail.format, 'WEBP')
        self.assertEqual(thumbnail.size, (400, 200))

    def test_it_keeps_proportions_of_a_portrait_photo(self):
        # === Arrange ===
        photo = self.make_photo(size=(600, 900))

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        self.assertEqual(self.stored(photo.thumbnail.name).size, (267, 400))

    def test_it_does_not_enlarge_a_small_photo(self):
        # === Arrange ===
        photo = self.make_photo(size=(300, 250))

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        self.assertEqual(self.stored(photo.thumbnail.name).size, (300, 250))

    def test_it_keeps_transparency(self):
        # === Arrange ===
        photo = self.make_photo(image_format='PNG', mode='RGBA', size=(800, 800), color=(255, 0, 0, 0))

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        self.assertEqual(self.stored(photo.thumbnail.name).mode, 'RGBA')

    def test_it_puts_thumbnail_next_to_the_original(self):
        # === Arrange ===
        photo = self.make_photo()

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        stem = photo.image.name.rsplit('/', 1)[1].rsplit('.', 1)[0]
        self.assertEqual(photo.thumbnail.name, f'listings/{self.listing.pk}/thumbs/{stem}.webp')

    def test_it_does_not_touch_the_original(self):
        # === Arrange ===
        photo = self.make_photo()
        before = self.stored(photo.image.name).size
        name = photo.image.name

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        self.assertEqual(photo.image.name, name)
        self.assertEqual(self.stored(photo.image.name).size, before)

    def test_it_is_safe_to_run_twice(self):
        # === Arrange ===
        photo = self.make_photo(size=(1000, 500))
        create_thumbnail(photo.pk)
        photo.refresh_from_db()
        first_name = photo.thumbnail.name
        files_before = default_storage.listdir(f'listings/{self.listing.pk}/thumbs')[1]

        # === Act ===
        create_thumbnail(photo.pk)

        # === Assert === (the same file, no duplicate with a random suffix)
        photo.refresh_from_db()
        self.assertEqual(photo.thumbnail.name, first_name)
        self.assertEqual(default_storage.listdir(f'listings/{self.listing.pk}/thumbs')[1], files_before)

    def test_it_does_nothing_if_the_photo_was_deleted(self):
        # === Arrange ===
        photo = self.make_photo()
        photo_id = photo.pk
        photo.delete()

        # === Act & Assert === (no exception)
        create_thumbnail(photo_id)

    def test_it_skips_a_photo_without_a_file(self):
        # === Arrange ===
        photo = ListingImage.objects.create(listing=self.listing, image='listings/missing.jpg')

        # === Act ===
        with self.assertLogs('listings.tasks', 'WARNING') as logs:
            create_thumbnail(photo.pk)

        # === Assert ===
        photo.refresh_from_db()
        self.assertFalse(photo.thumbnail)
        self.assertIn(f'Photo {photo.pk} has no file', logs.output[0])
