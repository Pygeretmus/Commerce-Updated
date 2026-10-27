from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .managers import NotificationManager


class Notification(models.Model):
    class Kind(models.TextChoices):
        OUTBID = 'outbid'
        WON = 'won'
        SOLD = 'sold'
        LOST = 'lost'
        ENDING_SOON = 'ending_soon'
        NEW_COMMENT = 'new_comment'
        LISTING_ENDED = 'listing_ended'
        CANCELLED = 'cancelled'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='+')
    # Small facts the text needs (an amount, a name), stored as they were at that moment
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    objects = NotificationManager()

    class Meta:
        ordering = ('-created_at', '-id')
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # "Ending soon" is sent once per person and lot, even if the task runs twice
            models.UniqueConstraint(
                fields=['recipient', 'listing'],
                condition=Q(kind='ending_soon'),
                name='notification_one_ending_soon',
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(F('recipient'), F('created_at').desc(), name='notification_recipient_idx'),
            # The badge counts unread ones: this index stays tiny because most rows are read
            models.Index(fields=['recipient'], condition=Q(read_at__isnull=True), name='notification_unread_idx'),
        ]

    def __str__(self):
        return f'{self.kind} for {self.recipient_id}'
