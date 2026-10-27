from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Listing


class IsListingSeller(BasePermission):
    """Reading a listing is open to everybody, changing it is for the seller."""

    message = 'Only the seller can change this listing.'

    def has_object_permission(self, request, view, obj: Listing) -> bool:
        return request.method in SAFE_METHODS or obj.seller_id == request.user.pk
