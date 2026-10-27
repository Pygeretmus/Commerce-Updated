from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .managers import ListingManager
from .services.pricing import next_min_bid


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Listing(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft'
        ACTIVE = 'active'
        ENDED = 'ended'
        CANCELLED = 'cancelled'

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='listings')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='listings')
    title = models.CharField(max_length=120)
    description = models.TextField()
    starting_price = models.DecimalField(max_digits=12, decimal_places=2)
    reserve_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    # Denormalised from the bids so that lists can sort and filter by price without a join.
    # They change only in place_bid(), under a lock on this row.
    current_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    bids_count = models.PositiveIntegerField(default=0, editable=False)
    # DO_NOTHING: SET_NULL would break the top_bid/bids_count constraint while a listing is
    # being deleted; bids are removed by the listing cascade and the FK check is deferred.
    top_bid = models.ForeignKey(
        'Bid', on_delete=models.DO_NOTHING, null=True, blank=True, editable=False, related_name='+'
    )
    published_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # The result of a closed auction: true when the top bidder won, false when it ended without
    # a winner (no bids, reserve not met, cancelled). null while the auction is not closed.
    sold = models.BooleanField(null=True, blank=True, editable=False)
    # Set once the "ending soon" notifications went out, so the beat task never repeats them
    ending_soon_notified_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = ListingManager()

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(condition=Q(starting_price__gt=0), name='listing_starting_price_positive'),
            models.CheckConstraint(
                condition=Q(reserve_price__isnull=True) | Q(reserve_price__gte=F('starting_price')),
                name='listing_reserve_gte_starting',
            ),
            models.CheckConstraint(
                condition=~Q(status='active') | Q(ends_at__isnull=False),
                name='listing_active_has_ends_at',
            ),
            models.CheckConstraint(
                condition=Q(current_price__gte=F('starting_price')), name='listing_current_price_gte_starting'
            ),
            # Only a closed auction has a result
            models.CheckConstraint(
                condition=Q(sold__isnull=True) | Q(status__in=['ended', 'cancelled']),
                name='listing_sold_only_when_closed',
            ),
            # A listing has a top bid exactly when it has bids
            models.CheckConstraint(
                condition=(Q(top_bid__isnull=True) & Q(bids_count=0))
                | (Q(top_bid__isnull=False) & Q(bids_count__gt=0)),
                name='listing_top_bid_matches_bids_count',
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            # What the closer task scans every minute
            models.Index(fields=['ends_at'], condition=Q(status='active'), name='listing_active_ends_at_idx'),
            models.Index(F('status'), F('published_at').desc(), name='listing_status_published_idx'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Without bids the price is the starting price. Keeping the rule here covers the admin
        # and the services alike; place_bid() sets top_bid, so it is left alone.
        if self.top_bid_id is None:
            self.current_price = self.starting_price
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'starting_price' in update_fields:
                kwargs['update_fields'] = {*update_fields, 'current_price'}
        super().save(*args, **kwargs)

    @property
    def next_min_bid(self) -> Decimal:
        return next_min_bid(self.starting_price, self.current_price, self.bids_count)

    @property
    def reserve_met(self) -> bool:
        return self.reserve_price is None or self.current_price >= self.reserve_price

    def is_ended(self, now=None) -> bool:
        """True when bids are no longer accepted, even if the closing task has not run yet."""
        if self.status != self.Status.ACTIVE:
            return self.status != self.Status.DRAFT
        return self.ends_at is not None and self.ends_at <= (now or timezone.now())

    def bidder_ids(self) -> set[int]:
        """Users who placed a bid (bids of deleted accounts are skipped)."""
        return set(Bid.objects.filter(listing=self, bidder__isnull=False).values_list('bidder_id', flat=True))

    def watcher_ids(self) -> set[int]:
        return set(Watch.objects.filter(listing=self).values_list('user_id', flat=True))


def listing_image_path(instance: 'ListingImage', filename: str) -> str:
    return f'listings/{instance.listing_id}/{filename}'


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=listing_image_path)
    # Filled in by a background task a moment after the upload; empty until then
    thumbnail = models.ImageField(upload_to=listing_image_path, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('position', 'id')

    def __str__(self):
        return f'{self.listing_id}#{self.position}'


class Bid(models.Model):
    """An accepted bid. Bids are never edited or deleted, they are the history of the auction."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bids')
    # null: the bidder deleted their account
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='bids')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-amount',)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(condition=Q(amount__gt=0), name='bid_amount_positive'),
            # Two equal bids can never both be stored, even if the lock around place_bid() fails
            models.UniqueConstraint(fields=['listing', 'amount'], name='bid_unique_amount_per_listing'),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(F('bidder'), F('created_at').desc(), name='bid_bidder_created_idx'),
        ]

    def __str__(self):
        return f'{self.amount} on listing {self.listing_id}'


class Comment(models.Model):
    """A question or an answer under a lot. Flat, not threaded; the seller's comments are the answers."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='comments')
    # null: the author deleted their account
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='comments')
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    # Soft delete: the row stays for moderation, the API no longer shows it
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('created_at', 'id')
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=['listing', 'created_at'], condition=Q(deleted_at__isnull=True), name='comment_listing_idx'
            ),
        ]

    def __str__(self):
        return f'{self.author_id} on listing {self.listing_id}'


class Watch(models.Model):
    """A lot on somebody's watchlist."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watches')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='watches')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=['user', 'listing'], name='watch_unique_user_listing'),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(F('user'), F('created_at').desc(), name='watch_user_created_idx'),
        ]
