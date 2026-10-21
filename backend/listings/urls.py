from django.urls import path

from .views.listings import (
    CategoryListView,
    ListingDetailView,
    ListingListCreateView,
)

app_name = 'listings'

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('listings/', ListingListCreateView.as_view(), name='listing-list'),
    path('listings/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
]
