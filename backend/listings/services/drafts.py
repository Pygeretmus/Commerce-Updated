import logging
from collections.abc import Iterable
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from PIL import Image, ImageOps
from rest_framework import serializers
from rest_framework.exceptions import APIException

from ..constants import DURATIONS_DAYS, MAX_DRAFTS
from ..models import Listing, ListingImage
from ..tasks import create_thumbnail

logger = logging.getLogger(__name__)

User = get_user_model()


class ListingNotEditable(APIException):
    status_code = 409
    default_detail = 'Only a draft can be changed or deleted.'
    default_code = 'not_editable'


def _lock_draft(listing: Listing, detail: str | None = None) -> Listing:
    """
    Re-reads the listing under a row lock and checks it is still a draft, so that
    a concurrent publish cannot slip in between the check and the write.
    """
    locked = Listing.objects.select_for_update().get(pk=listing.pk)
    require_draft(locked, detail)
    return locked


def require_draft(listing: Listing, detail: str | None = None) -> None:
    """Cheap early check for views (the services below check again under a lock)."""
    if listing.status != Listing.Status.DRAFT:
        raise ListingNotEditable(detail)


@transaction.atomic
def create_draft(seller: User, **data) -> Listing:
    # Lock the seller's row so two parallel requests cannot both pass the limit check
    User.objects.select_for_update().get(pk=seller.pk)
    if Listing.objects.filter(seller=seller, status=Listing.Status.DRAFT).count() >= MAX_DRAFTS:
        raise serializers.ValidationError(
            f'You can have at most {MAX_DRAFTS} drafts. Publish or delete one first.', code='draft_limit'
        )
    return Listing.objects.create(seller=seller, status=Listing.Status.DRAFT, **data)


@transaction.atomic
def update_draft(listing: Listing, **data) -> Listing:
    locked = _lock_draft(listing)
    for field, value in data.items():
        setattr(locked, field, value)
    # auto_now fields are only refreshed when listed in update_fields
    locked.save(update_fields=[*data, 'updated_at'])
    return locked


def _delete_files_after_commit(names: Iterable[str]) -> None:
    """Removes files from the storage only if the transaction that deleted their rows succeeded."""
    storage = ListingImage._meta.get_field('image').storage
    for name in names:
        transaction.on_commit(lambda name=name: storage.delete(name))


@transaction.atomic
def delete_draft(listing: Listing) -> None:
    locked = _lock_draft(listing)
    names = [name for pair in locked.images.values_list('image', 'thumbnail') for name in pair if name]
    locked.delete()
    _delete_files_after_commit(names)


def _schedule_thumbnail(photo_id: int) -> None:
    try:
        create_thumbnail.delay(photo_id)
    except Exception:
        # The preview is a nicety: a broker outage must not fail an upload that already succeeded.
        # Until a thumbnail exists the API falls back to the original photo.
        logger.exception('Could not schedule the thumbnail of photo %s', photo_id)


@transaction.atomic
def add_image(listing: Listing, image) -> ListingImage:
    locked = _lock_draft(listing)
    if locked.images.count() >= settings.LISTING_MAX_IMAGES:
        raise serializers.ValidationError(
            {'image': f'A listing can have at most {settings.LISTING_MAX_IMAGES} photos.'}, code='image_limit'
        )
    last = locked.images.aggregate(last=Max('position'))['last']
    photo = ListingImage(listing=locked, position=0 if last is None else last + 1)
    # The name is ours: whatever the client called the file never reaches the storage
    photo.image.save(image.name, image, save=False)
    try:
        photo.save()
    except Exception:
        photo.image.storage.delete(photo.image.name)
        raise
    transaction.on_commit(lambda: _schedule_thumbnail(photo.pk))
    return photo


@transaction.atomic
def delete_image(listing: Listing, photo: ListingImage) -> None:
    _lock_draft(listing)
    names = [name for name in (photo.image.name, photo.thumbnail.name) if name]
    photo.delete()
    _delete_files_after_commit(names)


@transaction.atomic
def reorder_images(listing: Listing, ids: list[int]) -> list[ListingImage]:
    locked = _lock_draft(listing)
    photos = {photo.pk: photo for photo in locked.images.all()}
    if len(ids) != len(set(ids)) or set(ids) != set(photos):
        raise serializers.ValidationError(
            {'ids': 'The list must contain every photo of the listing exactly once.'}, code='invalid_order'
        )
    for position, pk in enumerate(ids):
        photos[pk].position = position
    ListingImage.objects.bulk_update(photos.values(), ['position'])
    return sorted(photos.values(), key=lambda photo: photo.position)


def make_thumbnail(source):
    """Builds a WEBP preview of an already cleaned photo: its longer side is THUMBNAIL_SIZE px at most."""
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)
    image.thumbnail((settings.THUMBNAIL_SIZE, settings.THUMBNAIL_SIZE))  # keeps proportions, never enlarges
    buffer = BytesIO()
    image.save(buffer, format='WEBP', quality=80)
    return ContentFile(buffer.getvalue())


@transaction.atomic
def publish(listing: Listing, duration_days: int) -> Listing:
    """
    Puts a draft on sale: the auction starts now and runs for `duration_days`.

    Adding and removing photos lock the same listing row, so "has a photo" cannot become
    untrue between this check and the status change.
    """
    if duration_days not in DURATIONS_DAYS:
        raise serializers.ValidationError(
            {'duration_days': f'Choose one of: {", ".join(map(str, DURATIONS_DAYS))}.'}, code='invalid_choice'
        )
    locked = _lock_draft(listing, 'Only a draft can be published.')
    if not locked.images.exists():
        raise serializers.ValidationError('Add at least one photo before publishing.', code='no_photos')

    now = timezone.now()
    locked.status = Listing.Status.ACTIVE
    locked.published_at = now
    locked.ends_at = now + timedelta(days=duration_days)
    locked.save(update_fields=['status', 'published_at', 'ends_at', 'updated_at'])
    return locked
