from functools import partial
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F
from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from notifications.constants import ENDING_SOON_WINDOW
from notifications.models import Notification

from ..management.commands import seed_demo
from ..management.commands.seed_demo import BUYERS, DOMAIN, LOTS, PASSWORD, SELLERS
from ..models import Bid, Listing, ListingImage
from .helpers import make_active_listing

User = get_user_model()


def seed(*args) -> None:
    # Small pictures: the drawing is the slow part and nothing here looks at the pixels
    small = partial(seed_demo.make_photo, size=(500, 375))
    with mock.patch.object(seed_demo, 'make_photo', small):
        call_command('seed_demo', *args, stdout=StringIO())


class SeedDemoCommandTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # The command makes photos, so it is run once for all the read-only checks below.
        # Thumbnails are made by a task that waits for the commit: run those callbacks too.
        with cls.captureOnCommitCallbacks(execute=True):
            seed()
        cls.demo_users = User.objects.filter(email__endswith=f'@{DOMAIN}')
        cls.lots = Listing.objects.exclude(status=Listing.Status.DRAFT)

    def test_it_creates_every_demo_account_with_the_documented_password(self):
        # === Assert ===
        self.assertEqual(set(self.demo_users.values_list('username', flat=True)), {*SELLERS, *BUYERS})
        for user in self.demo_users:
            self.assertTrue(user.check_password(PASSWORD), user.username)

    def test_it_creates_the_catalogue_and_one_draft_for_my_lots(self):
        # === Assert ===
        self.assertEqual(self.lots.count(), len(LOTS))
        (draft,) = Listing.objects.filter(status=Listing.Status.DRAFT)
        self.assertEqual(draft.seller.username, 'alice')
        self.assertTrue(draft.images.exists())

    def test_every_lot_has_photos_with_thumbnails(self):
        # === Assert ===
        for listing in self.lots:
            with self.subTest(lot=listing.title):
                self.assertTrue(2 <= listing.images.count() <= 4)
        self.assertFalse(ListingImage.objects.filter(thumbnail='').exists())

    def test_the_price_of_every_lot_is_that_of_its_top_bid(self):
        # === Assert === (the bids went through place_bid, so the denormalised fields agree with the history)
        for listing in self.lots.select_related('top_bid'):
            with self.subTest(lot=listing.title):
                self.assertEqual(listing.bids_count, listing.bids.count())
                expected = listing.top_bid.amount if listing.top_bid else listing.starting_price
                self.assertEqual(listing.current_price, expected)

    def test_bids_happened_while_the_auction_was_running(self):
        # === Assert ===
        self.assertFalse(Bid.objects.filter(created_at__gt=F('listing__ends_at')).exists())
        self.assertFalse(Bid.objects.filter(created_at__lt=F('listing__published_at')).exists())
        self.assertFalse(Bid.objects.filter(created_at__gt=timezone.now()).exists())

    def test_finished_lots_are_closed_with_a_result_in_the_past(self):
        # === Act ===
        ended = list(Listing.objects.filter(status=Listing.Status.ENDED).select_related('top_bid'))

        # === Assert ===
        self.assertEqual(len(ended), sum(1 for lot in LOTS if lot[5] < 0))
        for listing in ended:
            with self.subTest(lot=listing.title):
                self.assertLessEqual(listing.closed_at, timezone.now())
                self.assertEqual(listing.sold, listing.top_bid_id is not None and listing.reserve_met)
        self.assertEqual(
            Notification.objects.filter(kind=Notification.Kind.WON).count(),
            Listing.objects.filter(sold=True).count(),
        )

    def test_it_leaves_one_lot_about_to_end_and_tells_its_people(self):
        # === Act ===
        now = timezone.now()
        soon = Listing.objects.filter(
            status=Listing.Status.ACTIVE, ends_at__gt=now, ends_at__lte=now + ENDING_SOON_WINDOW
        )

        # === Assert ===
        self.assertTrue(soon.filter(title='Silver pocket watch, running').exists())
        self.assertTrue(soon.filter(ending_soon_notified_at__isnull=False).exists())
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.ENDING_SOON).exists())


class SeedDemoResetTest(TestCase):
    def test_it_refuses_to_run_twice_without_reset(self):
        # === Arrange ===
        G(User, email=f'someone@{DOMAIN}')

        # === Act & Assert ===
        with self.assertRaisesMessage(CommandError, '--reset'):
            seed()

    def test_reset_rebuilds_the_demo_data_and_leaves_real_data_alone(self):
        # === Arrange ===
        with self.captureOnCommitCallbacks(execute=True):
            seed()
        storage = ListingImage._meta.get_field('image').storage
        old_files = [name for photo in ListingImage.objects.all() for name in (photo.image.name, photo.thumbnail.name)]
        real_user = G(User, email='real@example.com')
        real_lot = make_active_listing(seller=real_user)

        # === Act ===
        with self.captureOnCommitCallbacks(execute=True):
            seed('--reset')

        # === Assert ===
        self.assertEqual(User.objects.filter(email__endswith=f'@{DOMAIN}').count(), len(SELLERS) + len(BUYERS))
        self.assertEqual(Listing.objects.filter(seller__email__endswith=f'@{DOMAIN}').count(), len(LOTS) + 1)
        self.assertTrue(all(name and not storage.exists(name) for name in old_files))
        self.assertTrue(User.objects.filter(pk=real_user.pk).exists())
        self.assertTrue(Listing.objects.filter(pk=real_lot.pk).exists())


class MakePhotoTest(TestCase):
    def test_it_makes_a_valid_named_jpeg_in_every_palette(self):
        # === Act & Assert ===
        import random
        from io import BytesIO

        from PIL import Image

        for palette in seed_demo.PALETTES:
            with self.subTest(palette=palette):
                photo = seed_demo.make_photo(random.Random(1), palette, size=(500, 375))
                image = Image.open(BytesIO(photo.read()))
                self.assertEqual((image.format, image.size, photo.name), ('JPEG', (500, 375), 'demo.jpg'))

    def test_every_lot_uses_a_known_palette_and_category(self):
        # === Arrange ===
        from ..models import Category

        # === Act & Assert ===
        slugs = set(Category.objects.values_list('slug', flat=True))
        for title, slug, *_, palette in LOTS:
            with self.subTest(lot=title):
                self.assertIn(slug, slugs)
                self.assertIn(palette, seed_demo.PALETTES)
