from django.db import models
from django.db.models import Q


class ListingQuerySet(models.QuerySet):
    def with_images(self):
        return self.prefetch_related('images')

    def visible_to(self, user):
        """Everything is public except drafts, which only their seller can see."""
        visible = ~Q(status=self.model.Status.DRAFT)
        if user.is_authenticated:
            visible |= Q(seller=user)
        return self.filter(visible)


class ListingManager(models.Manager):
    def get_queryset(self):
        return ListingQuerySet(self.model, using=self._db)

    def with_images(self):
        return self.get_queryset().with_images()

    def visible_to(self, user):
        return self.get_queryset().visible_to(user)
