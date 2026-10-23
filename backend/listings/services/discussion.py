"""Questions and answers under a lot, and the watchlist."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from ..models import Comment, Listing


@transaction.atomic
def post_comment(listing: Listing, author, body: str) -> Comment:
    comment = Comment.objects.create(listing=listing, author=author, body=body)
    return comment


def delete_comment(comment: Comment, user) -> None:
    if comment.author_id != user.pk:
        raise PermissionDenied('You can only delete your own comments.')
    comment.deleted_at = timezone.now()
    comment.save(update_fields=['deleted_at'])
