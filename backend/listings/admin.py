from typing import ClassVar

from django.contrib import admin

from .models import Bid, Category, Listing, ListingImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields: ClassVar[dict[str, tuple[str, ...]]] = {'slug': ('name',)}
    search_fields = ('name',)


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'status', 'starting_price', 'ends_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'seller__username')
    raw_id_fields = ('seller',)
    readonly_fields = ('current_price', 'bids_count', 'top_bid')
    inlines = (ListingImageInline,)


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    """The bid history is read-only: bids are never edited or deleted by hand."""

    list_display = ('listing', 'bidder', 'amount', 'created_at')
    raw_id_fields = ('listing', 'bidder')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
