"""How an auction ends: by the clock (a Celery task), by the seller ("end now") or by cancelling."""

import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from ..models import Listing

logger = logging.getLogger(__name__)


def _lock(listing_id: int) -> Listing | None:
    return Listing.objects.select_for_update(of=('self',)).select_related('top_bid').filter(pk=listing_id).first()


def _close(listing: Listing, now: datetime, sold: bool) -> None:
    listing.status = Listing.Status.ENDED
    listing.closed_at = now
    listing.sold = sold
    listing.save(update_fields=['status', 'closed_at', 'sold', 'updated_at'])


def close_expired(listing_id: int, now: datetime | None = None) -> bool:
    """
    Ends the auction when its time is up. Safe to call any number of times: a lot that is already
    closed, still running (also after an anti-sniping extension) or unknown is left alone.
    The top bidder wins if the reserve price (when there is one) was reached.
    """
    now = now or timezone.now()
    with transaction.atomic():
        listing = _lock(listing_id)
        if listing is None or listing.status != Listing.Status.ACTIVE:
            return False
        if listing.ends_at is None or listing.ends_at > now:
            return False
        _close(listing, now, listing.top_bid_id is not None and listing.reserve_met)
        return True
