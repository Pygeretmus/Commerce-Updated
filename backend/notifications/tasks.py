import logging

from celery import shared_task
from django.utils import timezone

from .services import ENDING_SOON_WINDOW, notify_listing_ending_soon

logger = logging.getLogger(__name__)


@shared_task(queue='notifications')
def notify_ending_soon() -> int:
    """Beat task: finds lots that end within the hour and have not been announced yet."""
    from listings.models import Listing

    now = timezone.now()
    ids = Listing.objects.filter(
        status=Listing.Status.ACTIVE,
        ends_at__gt=now,
        ends_at__lte=now + ENDING_SOON_WINDOW,
        ending_soon_notified_at__isnull=True,
    ).values_list('pk', flat=True)
    total = 0
    for listing_id in ids:
        try:  # each lot in its own transaction: one failure does not block the others
            total += notify_listing_ending_soon(listing_id, now)
        except Exception:
            logger.exception('Could not send "ending soon" for listing %s', listing_id)
    return total
