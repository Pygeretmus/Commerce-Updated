from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db import connections
from django.db.models import Exists, OuterRef, Q
from django_filters.rest_framework import BooleanFilter, CharFilter, ChoiceFilter, FilterSet, NumberFilter
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated

from .models import Bid, Listing, Watch

# The same expression is used by the GIN index (migration 0007), so PostgreSQL can answer from the index
SEARCH_VECTOR = SearchVector('title', 'description', config='english')

# `ordering=<key>` of the lot list; the last field of every tuple makes the order stable
ORDERINGS = {
    'newest': ('-published_at', '-id'),
    'ending_soon': ('ends_at', 'id'),
    'price_asc': ('current_price', 'id'),
    'price_desc': ('-current_price', '-id'),
    'most_bids': ('-bids_count', '-id'),
}


class ListingFilter(FilterSet):
    """The query string of the lot list: `?q=vase&category=art&min_price=10&ordering=ending_soon`."""

    # Drafts and cancelled lots are never public, so they are not valid values here.
    # Without `status` the list shows active lots, or every status when `watching`/`bidding` is set.
    status = ChoiceFilter(
        choices=[(Listing.Status.ACTIVE.value, 'active'), (Listing.Status.ENDED.value, 'ended')],
        empty_label=None,
    )
    category = CharFilter(field_name='category__slug', help_text='Category slug')
    seller = CharFilter(field_name='seller__username', max_length=150, help_text='Username of the seller')
    min_price = NumberFilter(
        field_name='current_price', lookup_expr='gte', min_value=0, max_digits=12, decimal_places=2
    )
    max_price = NumberFilter(
        field_name='current_price', lookup_expr='lte', min_value=0, max_digits=12, decimal_places=2
    )
    q = CharFilter(method='filter_search', max_length=100, help_text='Words from the title or the description')
    watching = BooleanFilter(method='filter_watching', help_text='Only my watchlist (needs a login)')
    bidding = BooleanFilter(method='filter_bidding', help_text='Only lots I have bid on (needs a login)')
    ordering = ChoiceFilter(choices=[(key, key) for key in ORDERINGS], method='filter_ordering', empty_label=None)

    class Meta:
        model = Listing
        fields = ()  # every filter is declared above

    def filter_search(self, queryset, name, value):
        if connections[queryset.db].vendor != 'postgresql':
            # No full-text search here (e.g. SQLite): plain substring match, no stemming
            return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))
        # Full-text search with stemming ("watches" finds "watch"), answered by the GIN index
        return queryset.alias(search=SEARCH_VECTOR).filter(
            search=SearchQuery(value, config='english', search_type='websearch')
        )

    def filter_watching(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Exists(Watch.objects.filter(user=self.request.user, listing=OuterRef('pk'))))

    def filter_bidding(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Exists(Bid.objects.filter(bidder=self.request.user, listing=OuterRef('pk'))))

    def filter_ordering(self, queryset, name, value):
        return queryset.order_by(*ORDERINGS[value])

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        low, high = data.get('min_price'), data.get('max_price')
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError(
                {'min_price': 'The minimum price cannot be higher than the maximum.'}, code='invalid_range'
            )

        personal = bool(data.get('watching') or data.get('bidding'))
        if personal and not self.request.user.is_authenticated:
            raise NotAuthenticated('Log in to filter by your own watchlist or bids.')

        queryset = super().filter_queryset(queryset)

        # The defaults depend on other parameters, so they cannot live in a single filter
        if not data.get('status'):
            if personal:
                queryset = queryset.exclude(status=Listing.Status.DRAFT)
            else:
                queryset = queryset.filter(status=Listing.Status.ACTIVE)
        if not data.get('ordering'):
            queryset = queryset.order_by(*ORDERINGS['newest'])
        return queryset
