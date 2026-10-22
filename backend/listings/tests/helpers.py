from datetime import timedelta
from io import BytesIO
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django_dynamic_fixture import N
from PIL import Image

from ..models import Bid, Category, Listing, ListingImage


def make_listing(**kwargs) -> Listing:
    """Saves a draft in the 'art' category; pass fields to override (a published lot needs status and ends_at)."""
    fields: dict[str, Any] = {'category': Category.objects.get(slug='art'), 'seller': None, 'reserve_price': None}
    fields.update(kwargs)
    listing = N(Listing, **fields)
    listing.save()
    return listing


def make_active_listing(**kwargs) -> Listing:
    fields: dict[str, Any] = {
        'status': Listing.Status.ACTIVE,
        'published_at': timezone.now(),
        'ends_at': timezone.now() + timedelta(days=1),
    }
    fields.update(kwargs)
    return make_listing(**fields)


def make_image_file(
    image_format: str = 'JPEG',
    size: tuple[int, int] = (400, 300),
    mode: str = 'RGB',
    exif: Image.Exif | None = None,
    name: str | None = None,
    color: Any = 'red',
) -> SimpleUploadedFile:
    """A real image in memory, as a browser would upload it."""
    buffer = BytesIO()
    options = {'exif': exif} if exif is not None else {}
    Image.new(mode, size, color).save(buffer, image_format, **options)
    extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}[image_format]
    return SimpleUploadedFile(name or f'photo.{extension}', buffer.getvalue(), f'image/{extension}')


def make_exif(orientation: int = 1) -> Image.Exif:
    """EXIF with a camera name, an orientation and GPS coordinates."""
    exif = Image.Exif()
    exif[0x010F] = 'TestCamera'
    exif[0x0112] = orientation
    exif[0x8825] = {1: 'N', 2: (50.0, 27.0, 0.0), 3: 'E', 4: (30.0, 31.0, 0.0)}
    return exif


def make_listing_image(listing: Listing, position: int = 0) -> ListingImage:
    """A photo row with a real file in the storage."""
    photo = ListingImage(listing=listing, position=position)
    photo.image.save(f'photo{position}.jpg', ContentFile(make_image_file().read()), save=False)
    photo.save()
    return photo


def bid_on(listing: Listing, bidder, amount) -> Bid:
    """Places a bid through the real service (so the listing state stays consistent)."""
    from decimal import Decimal

    from listings.services.bidding import place_bid

    return place_bid(listing.pk, bidder, Decimal(amount))
