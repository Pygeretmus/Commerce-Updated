"""
Fills the database with a believable catalogue: sellers, buyers, lots with generated photos and bid
histories, a few finished auctions and one that ends in two minutes (so you can watch it close).

    python manage.py seed_demo            # first run
    python manage.py seed_demo --reset    # wipe the demo data and build it again

Every demo account has the password "demo-pass-123" and an @demo.example address.
"""

import random
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFilter

from listings.models import Bid, Category, Comment, Listing, ListingImage, Watch
from listings.services import drafts
from listings.services.bidding import BidRejected, place_bid
from listings.services.closing import close_expired
from notifications.constants import ENDING_SOON_WINDOW
from notifications.services.notify import notify_listing_ending_soon

User = get_user_model()

PASSWORD = 'demo-pass-123'
DOMAIN = 'demo.example'
SELLERS = ('alice', 'marcus', 'ingrid')
BUYERS = ('bob', 'carol', 'dmitri', 'elena', 'farid')

# (title, category slug, description, starting price, reserve or None, hours left, bids, palette)
# hours left < 0 means: the auction has ended (the number is how long ago)
LOTS = [
    (
        'Silver pocket watch, running',
        'jewelry',
        'Swiss movement, hand-engraved case, keeps good time. Comes with a short chain.',
        60,
        120,
        0.035,
        5,
        'steel',
    ),
    (
        'Victorian brass carriage clock',
        'antiques',
        'Eight-day movement, bevelled glass panels, original key. Small repair to the handle.',
        80,
        150,
        5,
        7,
        'brass',
    ),
    (
        'Oil on canvas: harbour at dusk',
        'art',
        'Signed and dated on the back. Painted in thick, warm strokes; unframed, 60 x 45 cm.',
        120,
        None,
        26,
        4,
        'dusk',
    ),
    (
        'Oak writing desk, circa 1890',
        'antiques',
        'Three drawers, green leather inlay, a few honest scratches. Dismantles for transport.',
        200,
        350,
        52,
        3,
        'oak',
    ),
    (
        'Linocut print, edition 12/50',
        'art',
        'Hand-pulled on cotton paper, pencil-signed. Two-colour print of a heron in reeds.',
        35,
        None,
        8,
        6,
        'forest',
    ),
    (
        'First edition atlas of the Baltic',
        'books',
        'Folding maps intact, light foxing at the margins. Cloth binding in good condition.',
        90,
        160,
        70,
        2,
        'paper',
    ),
    (
        'Vintage wool overcoat, size M',
        'clothing',
        'Heavy herringbone wool, satin lining, horn buttons. Dry-cleaned, no moth damage.',
        45,
        None,
        3,
        8,
        'slate',
    ),
    (
        'Restored reel-to-reel recorder',
        'electronics',
        'Serviced and tested, new belts and heads cleaned. Two speeds, warm sound.',
        150,
        260,
        30,
        5,
        'steel',
    ),
    (
        'Hand-thrown stoneware vase set',
        'home-garden',
        'Three vases with an ash glaze, each signed on the base. Food safe, never used.',
        40,
        None,
        12,
        3,
        'clay',
    ),
    (
        'Art deco sapphire ring',
        'jewelry',
        'Platinum-look setting, a calibre-cut sapphire flanked by small clear stones. Size N.',
        300,
        480,
        96,
        4,
        'ink',
    ),
    (
        'Bamboo fly rod, 8 feet',
        'sports',
        'Three-piece split cane rod in its cloth bag. Fresh varnish, new ferrules.',
        110,
        None,
        20,
        2,
        'forest',
    ),
    (
        'Wooden train set, 60 pieces',
        'toys',
        'Beech track, bridges, tunnels and six painted wagons. Complete, lightly played with.',
        25,
        None,
        9,
        9,
        'toy',
    ),
    (
        'Stamp album, 1930s Europe',
        'collectibles',
        'Around 600 stamps, mostly used, a few mint sets. Some hinges, album a little worn.',
        55,
        None,
        44,
        3,
        'paper',
    ),
    (
        'Cast-iron garden bench',
        'home-garden',
        'Two-seater with a slatted oak seat, repainted in dark green. Heavy, collect only.',
        70,
        None,
        120,
        1,
        'forest',
    ),
    (
        'Mechanical keyboard, hand-built',
        'electronics',
        'Brass plate, tactile switches, PBT caps. Includes a braided cable.',
        95,
        None,
        6,
        6,
        'ink',
    ),
    (
        'Silk scarf, hand-rolled hems',
        'clothing',
        'Abstract print in rust and teal, 90 cm square. Worn twice.',
        20,
        None,
        2,
        5,
        'dusk',
    ),
    (
        'Coin collection: 40 silver crowns',
        'collectibles',
        'Nineteenth and early twentieth century crowns, catalogued in a flat-pack folder.',
        400,
        650,
        160,
        2,
        'brass',
    ),
    (
        'Hand-painted rocking horse',
        'toys',
        'Solid ash frame, real-hair mane, leather saddle. Restored by a toy maker.',
        130,
        None,
        72,
        0,
        'toy',
    ),
    (
        'Abstract ceramic sculpture',
        'art',
        'Stacked glazed forms on a black base, 38 cm tall. One of three made.',
        220,
        300,
        15,
        0,
        'clay',
    ),
    (
        'Set of 12 pocket classics',
        'books',
        'Matching cloth spines, gilt titles, in a card slipcase. Pages clean.',
        30,
        None,
        28,
        1,
        'paper',
    ),
    # finished auctions
    (
        'Leather cricket bat, signed',
        'sports',
        'Willow blade, knocked in, signed by the club team. Grip replaced last season.',
        50,
        None,
        -30,
        6,
        'oak',
    ),
    (
        'Brass telescope on tripod',
        'antiques',
        'Three-draw telescope with leather grip, mahogany tripod. Optics clear.',
        140,
        400,
        -52,
        4,
        'brass',
    ),
    (
        'Enamel brooch, a pair of swallows',
        'jewelry',
        'Cold enamel on silver, pin intact. Boxed.',
        25,
        None,
        -80,
        0,
        'ink',
    ),
    (
        'Folding camp stool, canvas',
        'sports',
        'Ash legs, striped canvas seat, brass fittings.',
        15,
        None,
        -100,
        3,
        'slate',
    ),
]

# Colours for the generated "photographs": (background top, background bottom, shapes...)
PALETTES = {
    'steel': ('#c9d1d8', '#6e7b88', ['#2f3a45', '#e8edf1', '#9aa7b3']),
    'brass': ('#f1dfb0', '#a9803a', ['#5c3d12', '#fff4d6', '#c9a24d']),
    'dusk': ('#f6c28b', '#4a3b67', ['#2b2146', '#f8e3c3', '#c75b5b']),
    'oak': ('#e8d2ac', '#7b5230', ['#3d2713', '#f4e6cb', '#a8763f']),
    'forest': ('#d8e3c8', '#3f6249', ['#1f3a2a', '#f1f5e6', '#7da07b']),
    'paper': ('#f7f1e2', '#cdbf9c', ['#4a4033', '#fffaf0', '#a89a78']),
    'slate': ('#d7dbe0', '#4b5563', ['#1f2937', '#f3f4f6', '#8b95a5']),
    'clay': ('#f0d4c0', '#a35c3e', ['#5a2c1a', '#fbeee3', '#d08a68']),
    'ink': ('#d6d9ec', '#2b2f5a', ['#14173a', '#eef0fb', '#6f76c4']),
    'toy': ('#fbe3a5', '#d65a45', ['#2f5d8a', '#fff6dc', '#e9a23b']),
}


def make_photo(rng: random.Random, palette: str, size=(1200, 900)) -> ContentFile:
    """A soft, abstract "still life" in the colours of the palette. Not a photo, but it looks like a catalogue plate."""
    top, bottom, shapes = PALETTES[palette]
    width, height = size
    image = Image.new('RGB', size, top)
    draw = ImageDraw.Draw(image)
    top_rgb, bottom_rgb = (
        tuple(int(top[i : i + 2], 16) for i in (1, 3, 5)),
        tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5)),
    )
    for y in range(height):  # vertical gradient
        t = y / height
        draw.line(
            [(0, y), (width, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top_rgb, bottom_rgb, strict=True))
        )
    # a "table" line and a soft shadow, then three or four forms standing on it
    horizon = int(height * rng.uniform(0.62, 0.72))
    draw.rectangle([0, horizon, width, height], fill=shapes[0])
    shadow = Image.new('RGBA', size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    for _ in range(rng.randint(3, 4)):
        w = rng.randint(120, 300)
        h = rng.randint(180, 420)
        x = rng.randint(80, width - 80 - w)
        base = horizon + rng.randint(-10, 30)
        colour = rng.choice(shapes)
        shadow_draw.ellipse([x - 10, base - 12, x + w + 40, base + 24], fill=(0, 0, 0, 90))
        kind = rng.choice(('round', 'tall', 'plate'))
        if kind == 'round':
            shadow_draw.ellipse([x, base - w, x + w, base], fill=colour)
        elif kind == 'tall':
            shadow_draw.rounded_rectangle([x, base - h, x + w // 2, base], radius=w // 6, fill=colour)
        else:
            shadow_draw.ellipse([x, base - h // 5, x + w + 60, base], fill=colour)
    image = Image.alpha_composite(image.convert('RGBA'), shadow.filter(ImageFilter.GaussianBlur(1.2))).convert('RGB')
    buffer = BytesIO()
    image.save(buffer, 'JPEG', quality=84)
    return ContentFile(buffer.getvalue(), name='demo.jpg')  # add_image() gives the stored file its own name


class Command(BaseCommand):
    help = 'Creates demo users, lots with photos and bid histories (password for all: demo-pass-123).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete the demo data first and build it again')

    def handle(self, *args, **options):
        demo_users = User.objects.filter(email__endswith=f'@{DOMAIN}')
        if demo_users.exists() and not options['reset']:
            raise CommandError('Demo data already exists. Run with --reset to rebuild it.')
        if options['reset']:
            self.wipe(demo_users)

        # Photos and thumbnails are made right here, and nothing needs Redis to run the command
        from celery import current_app

        current_app.conf.task_always_eager = True
        layers = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
        with override_settings(CHANNEL_LAYERS=layers):
            self.seed(random.Random(2026))

    def wipe(self, demo_users) -> None:
        storage = ListingImage._meta.get_field('image').storage
        listings = Listing.objects.filter(seller__in=demo_users)
        for photo in ListingImage.objects.filter(listing__in=listings):
            for name in (photo.image.name, photo.thumbnail.name):
                if name:
                    storage.delete(name)
        with transaction.atomic():
            # Bids point at lots and lots point at their top bid: remove the pointers first
            listings.update(top_bid=None, bids_count=0)
            Bid.objects.filter(listing__in=listings).delete()
            listings.delete()
            demo_users.delete()
        self.stdout.write('Old demo data removed.')

    def seed(self, rng: random.Random) -> None:
        users = {
            name: User.objects.create_user(username=name, email=f'{name}@{DOMAIN}', password=PASSWORD)
            for name in (*SELLERS, *BUYERS)
        }
        sellers = [users[name] for name in SELLERS]
        buyers = [users[name] for name in BUYERS]
        categories = {category.slug: category for category in Category.objects.all()}
        now = timezone.now()

        for index, (title, slug, description, start, reserve, hours, bids, palette) in enumerate(LOTS):
            seller = sellers[index % len(sellers)]
            listing = drafts.create_draft(
                seller,
                title=title,
                description=description,
                category=categories[slug],
                starting_price=Decimal(start),
                reserve_price=Decimal(reserve) if reserve else None,
            )
            for _ in range(rng.randint(2, 4)):
                drafts.add_image(listing, make_photo(rng, palette))
            listing = drafts.publish(listing, 7)

            ended = hours < 0
            # Published a while ago; a finished lot ran for a day, a running one ends `hours` from now
            published_at = now - timedelta(hours=abs(hours) + 24 if ended else rng.randint(2, 70))
            ends_at = now - timedelta(hours=abs(hours)) if ended else now + timedelta(hours=hours)
            # While bids are placed the lot must still be open, so its end is moved to the past afterwards
            Listing.objects.filter(pk=listing.pk).update(published_at=published_at, ends_at=now + timedelta(days=1))

            self.place_bids(rng, listing, buyers, bids)
            self.spread_bids(listing, published_at, min(ends_at, now))
            Listing.objects.filter(pk=listing.pk).update(ends_at=ends_at)
            if ended:
                close_expired(listing.pk, now=ends_at + timedelta(seconds=1))

        self.add_social_life(rng, users)
        self.announce_ending_soon(now)
        # One draft, so the "My lots" page has something to show
        draft = drafts.create_draft(
            users['alice'],
            title='Walnut side table (draft)',
            description='Still photographing this one.',
            category=categories['antiques'],
            starting_price=Decimal(85),
        )
        drafts.add_image(draft, make_photo(rng, 'oak'))

        self.stdout.write(self.style.SUCCESS(f'Created {len(users)} users and {len(LOTS)} lots (+1 draft).'))
        self.stdout.write(f'Log in as {", ".join(users)} with the password "{PASSWORD}".')

    def place_bids(self, rng, listing, buyers, count) -> None:
        """Real bids through the service, so the prices, counters and "outbid" notifications are all genuine."""
        leader = None
        for _ in range(count):
            bidder = rng.choice([b for b in buyers if b != leader])
            listing.refresh_from_db()
            raise_by = Decimal(rng.choice((0, 0, 0.05, 0.1))).quantize(Decimal('0.01'))
            amount = listing.next_min_bid * (1 + raise_by)
            try:
                place_bid(listing.pk, bidder, amount.quantize(Decimal('0.01')))
            except BidRejected:
                continue
            leader = bidder

    def spread_bids(self, listing, start, end) -> None:
        """Gives the bids believable times: evenly between the start of the auction and `end`, oldest first."""
        bids = list(Bid.objects.filter(listing=listing).order_by('amount'))
        span = max((end - start).total_seconds() * 0.9, 600)
        for position, bid in enumerate(bids):
            moment = start + timedelta(seconds=span * (position + 1) / (len(bids) + 1))
            Bid.objects.filter(pk=bid.pk).update(created_at=min(moment, end))

    def announce_ending_soon(self, now) -> None:
        """What the beat task would have done by now: tell watchers and bidders of the lots ending within the hour."""
        soon = Listing.objects.filter(
            status=Listing.Status.ACTIVE, ends_at__gt=now, ends_at__lte=now + ENDING_SOON_WINDOW
        )
        for listing in soon:
            notify_listing_ending_soon(listing.pk, now)

    def add_social_life(self, rng, users) -> None:
        active = list(Listing.objects.filter(status=Listing.Status.ACTIVE).order_by('id'))
        questions = (
            'Is there any damage not shown in the photos?',
            'Can you ship abroad?',
            'Is the reserve close to the starting price?',
        )
        answers = (
            'Only what is described. Happy to send more photos.',
            "Yes, at the buyer's cost.",
            'I would not say, sorry.',
        )
        for listing in active[:5]:
            asker = users[rng.choice(BUYERS)]
            Comment.objects.create(listing=listing, author=asker, body=rng.choice(questions))
            Comment.objects.create(listing=listing, author=listing.seller, body=rng.choice(answers))
        for name in ('bob', 'carol'):
            for listing in rng.sample(active, 4):
                Watch.objects.get_or_create(user=users[name], listing=listing)
