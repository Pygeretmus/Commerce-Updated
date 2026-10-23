from django.test import TestCase
from django_dynamic_fixture import G

from ..models import Category, Listing, ListingImage


class ListingImageTest(TestCase):
    def test_it_orders_images_by_position(self):
        # === Arrange ===
        listing = G(Listing, category=Category.objects.get(slug='art'), seller=None, reserve_price=None)
        second = ListingImage.objects.create(listing=listing, image='b.jpg', position=1)
        first = ListingImage.objects.create(listing=listing, image='a.jpg', position=0)

        # === Act ===
        images = list(listing.images.all())

        # === Assert ===
        self.assertEqual(images, [first, second])

    def test_it_deletes_images_with_listing(self):
        listing = G(Listing, category=Category.objects.get(slug='art'), seller=None, reserve_price=None)
        ListingImage.objects.create(listing=listing, image='a.jpg')

        listing.delete()

        self.assertEqual(ListingImage.objects.count(), 0)
