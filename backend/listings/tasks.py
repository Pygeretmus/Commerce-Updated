import logging
from pathlib import PurePosixPath

from celery import shared_task
from django.db import transaction

from .models import ListingImage

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
