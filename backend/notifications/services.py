from collections.abc import Iterable
from decimal import Decimal

from .models import Notification


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
