from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from configuration.pagination import StandardPagination

from ..models import Category, Listing, ListingImage
from ..permissions import IsListingSeller
from ..serializers import (
    CategorySerializer,
    ListingDetailSerializer,
    ListingImageOrderSerializer,
    ListingImageSerializer,
    ListingImageUploadSerializer,
    ListingListSerializer,
    ListingWriteSerializer,
)
from ..services.drafts import add_image, delete_draft, delete_image, reorder_images, require_draft


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


class DraftListingMixin:
    """
    Finds the listing a photo endpoint works on. The order of the answers matters:
    404 (a draft of somebody else), 403 (somebody else's lot), 409 (not a draft any more).
    """

    permission_classes = (IsAuthenticated, IsListingSeller)
    not_draft_message: str | None = None

    def get_listing(self) -> Listing:
        listing = get_object_or_404(Listing.objects.visible_to(self.request.user), pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, listing)
        require_draft(listing, self.not_draft_message)
        return listing


@extend_schema_view(
    post=extend_schema(
        request={'multipart/form-data': ListingImageUploadSerializer}, responses={201: ListingImageSerializer}
    )
)
class ListingImageCreateView(DraftListingMixin, WriteThrottleMixin, GenericAPIView):
    """Uploads one photo to a draft."""

    throttle_scope = 'image_upload'
    serializer_class = ListingImageUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        listing = self.get_listing()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = add_image(listing, serializer.validated_data['image'])
        data = ListingImageSerializer(photo, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(responses={204: None})
class ListingImageDetailView(DraftListingMixin, WriteThrottleMixin, GenericAPIView):
    """Removes a photo from a draft."""

    throttle_scope = 'image_upload'
    serializer_class = ListingImageSerializer

    def delete(self, request, *args, **kwargs):
        listing = self.get_listing()
        photo = get_object_or_404(ListingImage, pk=self.kwargs['image_id'], listing=listing)
        delete_image(listing, photo)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    put=extend_schema(request=ListingImageOrderSerializer, responses={200: ListingImageSerializer(many=True)})
)
class ListingImageOrderView(DraftListingMixin, WriteThrottleMixin, GenericAPIView):
    """Sets the order of the photos of a draft: `ids` lists every photo once, first is the cover."""

    throttle_scope = 'image_upload'
    serializer_class = ListingImageOrderSerializer

    def put(self, request, *args, **kwargs):
        listing = self.get_listing()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photos = reorder_images(listing, serializer.validated_data['ids'])
        data = ListingImageSerializer(photos, many=True, context=self.get_serializer_context()).data
        return Response(data)
