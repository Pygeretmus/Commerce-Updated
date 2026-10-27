"""How an auction ends: by the clock (a Celery task), by the seller ("end now") or by cancelling."""

from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from notifications.models import Notification
from notifications.realtime import push_to_listing
from notifications.services import notify

from ..models import Listing
from .state import listing_ended_event


class ListingStateConflict(APIException):
    """The listing is not in a state where this action makes sense (HTTP 409). `code` tells which rule."""

    status_code = 409
    default_detail = 'This action is not possible for the listing in its current state.'
    default_code = 'invalid_state'


def _lock(listing_id: int) -> Listing | None:
    return Listing.objects.select_for_update(of=('self',)).select_related('top_bid').filter(pk=listing_id).first()


def _announce_end(listing: Listing) -> None:
    """Notifications for everybody who cares, one kind each, then the push to the lot's page."""
    seller = listing.seller_id
    bidders = listing.bidder_ids()
    watchers = listing.watcher_ids() - bidders - {seller}
    amount = listing.current_price
    if listing.sold:
        winner = listing.top_bid.bidder_id
        notify([winner], Notification.Kind.WON, listing, amount=amount)
        notify([seller], Notification.Kind.SOLD, listing, amount=amount)
        notify(bidders - {winner}, Notification.Kind.LOST, listing)
        notify(watchers - {winner}, Notification.Kind.LISTING_ENDED, listing, sold=True)
    else:
        notify({seller} | bidders | watchers, Notification.Kind.LISTING_ENDED, listing, sold=False)
    push_to_listing(listing.pk, listing_ended_event(listing))


def _close(listing: Listing, now: datetime, *, sold: bool) -> None:
    listing.status = Listing.Status.ENDED
    listing.closed_at = now
    listing.sold = sold
    listing.save(update_fields=['status', 'closed_at', 'sold', 'updated_at'])
    _announce_end(listing)


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
        _close(listing, now, sold=listing.top_bid_id is not None and listing.reserve_met)
        return True


def end_now(listing_id: int, now: datetime | None = None) -> Listing:
    """The seller accepts the current top bid: the auction ends at once and the top bidder wins."""
    now = now or timezone.now()
    with transaction.atomic():
        listing = _lock(listing_id)
        if listing is None or listing.status != Listing.Status.ACTIVE:
            raise ListingStateConflict('Only an active listing can be ended.', 'not_active')
        if listing.bids_count == 0:
            raise ListingStateConflict('There are no bids yet. Cancel the listing instead.', 'no_bids')
        listing.ends_at = min(listing.ends_at, now)
        listing.save(update_fields=['ends_at'])
        _close(listing, now, sold=True)
        return listing


def cancel(listing_id: int, now: datetime | None = None) -> Listing:
    """The seller withdraws a lot. Only possible while there are no bids."""
    now = now or timezone.now()
    with transaction.atomic():
        listing = _lock(listing_id)
        if listing is None or listing.status != Listing.Status.ACTIVE:
            raise ListingStateConflict('Only an active listing can be cancelled.', 'not_active')
        if listing.bids_count > 0:
            raise ListingStateConflict('A listing with bids cannot be cancelled.', 'has_bids')
        listing.status = Listing.Status.CANCELLED
        listing.closed_at = now
        listing.sold = False
        listing.save(update_fields=['status', 'closed_at', 'sold', 'updated_at'])
        notify(listing.watcher_ids() - {listing.seller_id}, Notification.Kind.CANCELLED, listing)
        push_to_listing(listing.pk, listing_ended_event(listing))
        return listing
