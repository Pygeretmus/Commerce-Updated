from django.urls import path

from .consumers import ListingConsumer

websocket_urlpatterns = [
    path('ws/listings/<int:listing_id>/', ListingConsumer.as_asgi()),
]
