from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .managers import ListingManager


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
    current_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    published_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
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
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.Status.DRAFT:
            self.current_price = self.starting_price
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'starting_price' in update_fields:
                kwargs['update_fields'] = {*update_fields, 'current_price'}
        super().save(*args, **kwargs)


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
