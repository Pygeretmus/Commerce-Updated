from django.urls import path

from .views.listings import (
    CategoryListView,
    ListingDetailView,
    ListingListView,
)

app_name = 'listings'

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('listings/', ListingListView.as_view(), name='listing-list'),
    path('listings/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
]
