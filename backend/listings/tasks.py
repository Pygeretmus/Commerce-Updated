import logging
from pathlib import PurePosixPath

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Listing, ListingImage
from .services.closing import close_expired

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3, queue='images')
def create_thumbnail(image_id: int) -> None:
    """
    Makes the preview of a photo. Safe to run twice: the second run sees the thumbnail
    and does nothing, and the row lock stops two workers from making it at the same time.
    """
    with transaction.atomic():
        photo = ListingImage.objects.select_for_update().filter(pk=image_id).first()
        if photo is None or photo.thumbnail:
            return  # the photo was deleted in the meantime, or the work is already done
        try:
            with photo.image.open('rb') as original:
                from .services.drafts import make_thumbnail

                thumbnail = make_thumbnail(original)
        except FileNotFoundError:
            logger.warning('Photo %s has no file in the storage, thumbnail skipped', image_id)
            return
        stem = PurePosixPath(photo.image.name).stem
        photo.thumbnail.save(f'thumbs/{stem}.webp', thumbnail, save=False)
        photo.save(update_fields=['thumbnail'])


@shared_task(queue='commerce')
def close_expired_listings() -> int:
    """
    Beat task, runs every 30 seconds: ends every active lot whose time is up.
    The partial index listing_active_ends_at_idx makes the scan cheap. Returns how many were closed.
    """
    now = timezone.now()
    ids = Listing.objects.filter(status=Listing.Status.ACTIVE, ends_at__lte=now).values_list('pk', flat=True)
    closed = 0
    for listing_id in ids:
        try:  # one transaction per lot: a failure in one does not block the rest
            closed += close_expired(listing_id, now)
        except Exception:
            logger.exception('Could not close listing %s', listing_id)
    return closed
