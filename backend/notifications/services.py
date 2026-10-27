from collections.abc import Iterable
from decimal import Decimal

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
