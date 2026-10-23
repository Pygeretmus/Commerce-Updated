from django.urls import path

from .views.bids import BidListCreateView
from .views.listings import (
    CategoryListView,
    ListingCancelView,
    ListingDetailView,
    ListingEndNowView,
    ListingImageCreateView,
    ListingImageDetailView,
    ListingImageOrderView,
    ListingListCreateView,
    ListingPublishView,
)

app_name = 'listings'

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('listings/', ListingListCreateView.as_view(), name='listing-list'),
    path('listings/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
    path('listings/<int:pk>/publish/', ListingPublishView.as_view(), name='listing-publish'),
    path('listings/<int:pk>/cancel/', ListingCancelView.as_view(), name='listing-cancel'),
    path('listings/<int:pk>/end_now/', ListingEndNowView.as_view(), name='listing-end-now'),
    path('listings/<int:pk>/images/', ListingImageCreateView.as_view(), name='listing-image-list'),
    path('listings/<int:pk>/images/order/', ListingImageOrderView.as_view(), name='listing-image-order'),
    path('listings/<int:pk>/images/<int:image_id>/', ListingImageDetailView.as_view(), name='listing-image-detail'),
    path('listings/<int:pk>/bids/', BidListCreateView.as_view(), name='bid-list'),
]
