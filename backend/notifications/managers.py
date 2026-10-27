from django.db import models


class NotificationQuerySet(models.QuerySet):
    def unread_for(self, user):
        return self.filter(recipient=user, read_at__isnull=True)


class NotificationManager(models.Manager):
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)

    def unread_for(self, user):
        return self.get_queryset().unread_for(user)
