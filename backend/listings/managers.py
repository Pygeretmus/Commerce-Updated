from django.db import models
from django.db.models import Case, CharField, Max, Q, Value, When


class ListingQuerySet(models.QuerySet):
    def with_images(self):
        return self.prefetch_related('images')

    def visible_to(self, user):
        """Everything is public except drafts, which only their seller can see."""
        visible = ~Q(status=self.model.Status.DRAFT)
        if user.is_authenticated:
            visible |= Q(seller=user)
        return self.filter(visible)

    def bid_on_by(self, user):
        """
        The lots the user has bid on, one row each, with the highest amount they offered (`my_highest_bid`)
        and where they stand (`my_status`): winning/outbid while the lot runs, won/lost afterwards.
        """
        leading = Q(top_bid__bidder=user)
        return (
            self.filter(bids__bidder=user)
            .annotate(my_highest_bid=Max('bids__amount'), last_bid_at=Max('bids__created_at'))
            .annotate(
                my_status=Case(
                    When(Q(status=self.model.Status.ACTIVE) & leading, then=Value('winning')),
                    When(status=self.model.Status.ACTIVE, then=Value('outbid')),
                    When(Q(sold=True) & leading, then=Value('won')),
                    default=Value('lost'),
                    output_field=CharField(),
                )
            )
            .select_related('seller', 'category', 'top_bid')
            .with_images()
        )


class ListingManager(models.Manager):
    def get_queryset(self):
        return ListingQuerySet(self.model, using=self._db)

    def with_images(self):
        return self.get_queryset().with_images()

    def visible_to(self, user):
        return self.get_queryset().visible_to(user)

    def bid_on_by(self, user):
        return self.get_queryset().bid_on_by(user)
