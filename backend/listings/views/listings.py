from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from configuration.pagination import StandardPagination

from ..models import Category, Listing
from ..permissions import IsListingSeller
from ..serializers import (
    CategorySerializer,
    ListingDetailSerializer,
    ListingListSerializer,
    ListingWriteSerializer,
)
from ..services.drafts import delete_draft


class WriteThrottleMixin:
    """Throttles only the writing methods, reads stay on the global anon/user rates."""

    throttle_scope = 'listing_write'

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method not in SAFE_METHODS:
            throttles.append(ScopedRateThrottle())
        return throttles


class CategoryListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    pagination_class = None


@extend_schema_view(
    create=extend_schema(request=ListingWriteSerializer, responses={201: ListingDetailSerializer}),
)
class ListingListCreateView(WriteThrottleMixin, ListCreateAPIView):
    pagination_class = StandardPagination
    queryset = Listing.objects.select_related('seller', 'category').with_images()

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == 'POST' else [AllowAny()]

    def get_serializer_class(self):
        return ListingWriteSerializer if self.request.method == 'POST' else ListingListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.save()
        data = ListingDetailSerializer(listing, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    partial_update=extend_schema(request=ListingWriteSerializer, responses={200: ListingDetailSerializer}),
    update=extend_schema(exclude=True),
)
class ListingDetailView(WriteThrottleMixin, RetrieveUpdateDestroyAPIView):
    """One lot. Drafts exist only for their seller (404 for everyone else) and are the only editable state."""

    http_method_names = ('get', 'patch', 'delete', 'head', 'options')

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsListingSeller()]

    def get_serializer_class(self):
        return ListingDetailSerializer if self.request.method in SAFE_METHODS else ListingWriteSerializer

    def get_queryset(self):
        user = self.request.user
        return Listing.objects.visible_to(user).select_related('seller', 'category').with_images()

    def update(self, request, *args, **kwargs):
        listing = self.get_object()
        serializer = ListingWriteSerializer(
            listing, data=request.data, partial=True, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        listing = serializer.save()
        return Response(ListingDetailSerializer(listing, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance: Listing) -> None:
        delete_draft(instance)
