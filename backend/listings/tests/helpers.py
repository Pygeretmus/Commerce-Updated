from datetime import timedelta
from typing import Any

from django.utils import timezone
from django_dynamic_fixture import N

from ..models import Category, Listing


def make_listing(**kwargs) -> Listing:
    """Saves a draft in the 'art' category; pass fields to override (a published lot needs status and ends_at)."""
    fields: dict[str, Any] = {'category': Category.objects.get(slug='art'), 'seller': None, 'reserve_price': None}
    fields.update(kwargs)
    listing = N(Listing, **fields)
    listing.save()
    return listing


def make_active_listing(**kwargs) -> Listing:
    fields: dict[str, Any] = {
        'status': Listing.Status.ACTIVE,
        'published_at': timezone.now(),
        'ends_at': timezone.now() + timedelta(days=1),
    }
    fields.update(kwargs)
    return make_listing(**fields)
