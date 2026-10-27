from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .constants import ENDING_SOON_WINDOW
from .models import Notification


def render_text(kind: str, title: str, data: dict) -> str:
    amount = data.get('amount')
    match kind:
        case Notification.Kind.OUTBID:
            return f'You were outbid on "{title}". The price is now ${amount}.'
        case Notification.Kind.WON:
            return f'You won "{title}" for ${amount}.'
        case Notification.Kind.SOLD:
            return f'Your lot "{title}" sold for ${amount}.'
        case Notification.Kind.LOST:
            return f'"{title}" has ended and you did not win.'
        case Notification.Kind.ENDING_SOON:
            return f'"{title}" ends in less than an hour.'
        case Notification.Kind.NEW_COMMENT:
            return f'{data.get("author") or "Someone"} commented on "{title}".'
        case Notification.Kind.CANCELLED:
            return f'"{title}" was cancelled by the seller.'
        case Notification.Kind.LISTING_ENDED:
            return f'"{title}" has ended' + ('.' if data.get('sold') else ' without a sale.')
    return title


def notify(recipients: Iterable[int | None], kind: str, listing, **data) -> list[Notification]:
    """
    Creates one notification per recipient in the CURRENT transaction (so a rolled-back bid leaves none
    behind). `None` recipients (deleted accounts) are skipped.
    """
    ids = {pk for pk in recipients if pk is not None}
    if not ids:
        return []
    clean = {key: format(value, '.2f') if isinstance(value, Decimal) else value for key, value in data.items()}
    created = Notification.objects.bulk_create(
        [Notification(recipient_id=pk, kind=kind, listing=listing, data=clean) for pk in sorted(ids)]
    )
    return created


@transaction.atomic
def notify_listing_ending_soon(listing_id: int, now: datetime | None = None) -> int:
    """Tells watchers and bidders that a lot ends within the hour, once. Returns how many were notified."""
    from listings.models import Listing

    now = now or timezone.now()
    listing = Listing.objects.select_for_update().filter(pk=listing_id).first()
    if (
        listing is None
        or listing.status != Listing.Status.ACTIVE
        or listing.ending_soon_notified_at is not None
        or listing.ends_at is None
        or not (now < listing.ends_at <= now + ENDING_SOON_WINDOW)
    ):
        return 0
    listing.ending_soon_notified_at = now
    listing.save(update_fields=['ending_soon_notified_at', 'updated_at'])

    people = (listing.watcher_ids() | listing.bidder_ids()) - {listing.seller_id}
    return len(notify(people, Notification.Kind.ENDING_SOON, listing))
