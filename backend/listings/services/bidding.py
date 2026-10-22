from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from ..constants import CENT, MAX_BID, SNIPING_WINDOW
from ..models import Bid, Listing

User = get_user_model()


class BidRejected(APIException):
    """A bid broke a rule. `code` tells which one, the message tells the user what to do."""

    status_code = 400
    default_detail = 'The bid was rejected.'
    default_code = 'bid_rejected'

    def __init__(self, detail: str, code: str, min_bid: Decimal | None = None):
        super().__init__(detail, code)
        self.min_bid = min_bid


def place_bid(listing_id: int, bidder: User, amount: Decimal, *, now: datetime | None = None) -> Bid:
    """
    Places a bid, or raises BidRejected. Raises Listing.DoesNotExist for an unknown listing.

    Everything happens in one transaction with the listing row locked, so two bidders can never
    both be checked against the same old price: the second one waits, then sees the new price.
    """
    if amount <= 0 or amount > MAX_BID or amount != amount.quantize(CENT):
        raise BidRejected('Enter an amount in dollars and cents, for example 12.50.', 'invalid_amount')

    with transaction.atomic():
        # of=('self',): lock only the listing row (PostgreSQL cannot lock the nullable side of a join)
        listing = Listing.objects.select_for_update(of=('self',)).select_related('top_bid').get(pk=listing_id)
        now = now or timezone.now()

        # 1. The auction is open. ends_at is checked too: the task that closes auctions can lag.
        if listing.status != Listing.Status.ACTIVE or listing.ends_at is None or listing.ends_at <= now:
            raise BidRejected('This auction is not open for bids.', 'auction_closed')

        # 2. Not the seller, and not the one who already leads
        if listing.seller_id == bidder.pk:
            raise BidRejected('You cannot bid on your own listing.', 'own_listing')
        if listing.top_bid is not None and listing.top_bid.bidder_id == bidder.pk:
            raise BidRejected('You already have the highest bid.', 'already_top_bidder')

        # 3. Enough money
        minimum = listing.next_min_bid
        if amount < minimum:
            raise BidRejected(f'Your bid is too low. The minimum is {minimum}.', 'bid_too_low', min_bid=minimum)

        # 4. Record it and move the listing to the new state
        bid = Bid.objects.create(listing=listing, bidder=bidder, amount=amount)
        listing.current_price = amount
        listing.bids_count += 1
        listing.top_bid = bid
        if listing.ends_at - now <= SNIPING_WINDOW:
            listing.ends_at = now + SNIPING_WINDOW
        listing.save(update_fields=['current_price', 'bids_count', 'top_bid', 'ends_at', 'updated_at'])

        return bid
