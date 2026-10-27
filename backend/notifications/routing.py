from django.urls import path

from .services.consumers import ListingConsumer, UserConsumer

websocket_urlpatterns = [
    path('ws/listings/<int:listing_id>/', ListingConsumer.as_asgi()),
    path('ws/me/', UserConsumer.as_asgi()),
]
