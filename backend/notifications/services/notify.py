from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..constants import ENDING_SOON_WINDOW
from ..models import Notification
from ..serializers import NotificationSerializer
from .realtime import push_to_user


def notify(recipients: Iterable[int | None], kind: str, listing, **data) -> list[Notification]:
    """
    Creates one notification per recipient in the CURRENT transaction (so a rolled-back bid leaves none
    behind) and pushes them to their owners' browsers after the commit. `None` recipients (deleted accounts)
    are skipped.
    """
    ids = {pk for pk in recipients if pk is not None}
    if not ids:
        return []
    clean = {key: format(value, '.2f') if isinstance(value, Decimal) else value for key, value in data.items()}
    created = Notification.objects.bulk_create(
        [Notification(recipient_id=pk, kind=kind, listing=listing, data=clean) for pk in sorted(ids)]
    )
    for notification in created:
        notification.listing = listing  # the serializer reads the title without a query
        # The same serializer as the REST list, so a pushed notification has exactly the shape of a fetched one
        payload = {'type': 'notification', **NotificationSerializer(notification).data}
        push_to_user(notification.recipient_id, payload)
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
