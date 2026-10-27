"""Questions and answers under a lot, and the watchlist."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from notifications.constants import MAX_THREAD_NOTIFICATIONS
from notifications.models import Notification
from notifications.services import notify

from ..models import Comment, Listing, Watch


@transaction.atomic
def post_comment(listing: Listing, author, body: str) -> Comment:
    comment = Comment.objects.create(listing=listing, author=author, body=body)
    if author.pk == listing.seller_id:
        # The seller answers: everybody who asked something hears about it
        asked = (
            Comment.objects.filter(listing=listing, deleted_at__isnull=True)
            .exclude(author=author)
            .values_list('author_id', flat=True)
            .distinct()[:MAX_THREAD_NOTIFICATIONS]
        )
        recipients = set(asked)
    else:
        recipients = {listing.seller_id}
    notify(recipients, Notification.Kind.NEW_COMMENT, listing, author=author.username)
    return comment


def delete_comment(comment: Comment, user) -> None:
    if comment.author_id != user.pk:
        raise PermissionDenied('You can only delete your own comments.')
    comment.deleted_at = timezone.now()
    comment.save(update_fields=['deleted_at'])


def watch(listing: Listing, user) -> None:
    """Idempotent: watching twice is fine, and two parallel requests cannot create a duplicate."""
    Watch.objects.get_or_create(user=user, listing=listing)


def unwatch(listing: Listing, user) -> None:
    Watch.objects.filter(user=user, listing=listing).delete()
