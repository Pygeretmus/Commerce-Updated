from rest_framework.permissions import BasePermission

from .models import Listing


class IsListingSeller(BasePermission):
    message = 'Only the seller can change this listing.'

    def has_object_permission(self, request, view, obj: Listing) -> bool:
        return obj.seller_id == request.user.pk
