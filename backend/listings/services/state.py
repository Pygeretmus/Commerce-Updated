"""The small public picture of an auction (price, leader, end time). One shape for the API and for WebSocket events."""

from datetime import UTC, datetime

from django.utils import timezone

from ..models import Listing
from .masking import mask_name


def iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat().replace('+00:00', 'Z') if moment else None


def leader_of(listing: Listing) -> str | None:
    """The masked name of the top bidder. Reads top_bid.bidder, so select_related them in lists."""
    top = listing.top_bid
    return mask_name(top.bidder.username) if top is not None and top.bidder is not None else None


def money(value) -> str:
    return f'{value:.2f}'


def state_of(listing: Listing, leader: str | None = None) -> dict:
    return {
        'current_price': money(listing.current_price),
        'bids_count': listing.bids_count,
        'next_min_bid': money(listing.next_min_bid),
        'ends_at': iso(listing.ends_at),
        'leader': leader if leader is not None else leader_of(listing),
        'server_time': iso(timezone.now()),
    }


def listing_ended_event(listing: Listing) -> dict:
    sold = bool(listing.sold)
    return {
        'type': 'listing_ended',
        'listing_id': listing.pk,
        'status': listing.status,
        'sold': sold,
        'final_price': money(listing.current_price),
        'winner': leader_of(listing) if sold else None,
        'closed_at': iso(listing.closed_at),
        'server_time': iso(timezone.now()),
    }


def price_update_event(listing: Listing, leader: str | None = None) -> dict:
    return {'type': 'price_update', 'listing_id': listing.pk, **state_of(listing, leader)}
