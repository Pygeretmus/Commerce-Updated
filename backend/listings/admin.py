from typing import ClassVar

from django.contrib import admin

from .models import Category, Listing, ListingImage


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
    readonly_fields = ('current_price',)
    inlines = (ListingImageInline,)
