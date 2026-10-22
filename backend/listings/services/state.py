"""The small public picture of an auction (price, leader, end time). One shape for the API and for WebSocket events."""

from datetime import UTC, datetime

from ..models import Listing
from .masking import mask_name


def iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat().replace('+00:00', 'Z') if moment else None


def leader_of(listing: Listing) -> str | None:
    """The masked name of the top bidder. Reads top_bid.bidder, so select_related them in lists."""
    top = listing.top_bid
    return mask_name(top.bidder.username) if top is not None and top.bidder is not None else None
