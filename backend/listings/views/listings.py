from django.db.models import BooleanField, Exists, OuterRef, Value
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from configuration.pagination import StandardPagination

from ..filters import ListingFilter
from ..models import Bid, Category, Listing, ListingImage, Watch
from ..permissions import IsListingSeller
from ..serializers import (
    CategorySerializer,
    ListingDetailSerializer,
    ListingImageOrderSerializer,
    ListingImageSerializer,
    ListingImageUploadSerializer,
    ListingListSerializer,
    ListingPublishSerializer,
    ListingWriteSerializer,
)
from ..services.closing import cancel, end_now
from ..services.drafts import add_image, delete_draft, delete_image, publish, reorder_images, require_draft


class CategoryListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    pagination_class = None


@extend_schema_view(
    create=extend_schema(request=ListingWriteSerializer, responses={201: ListingDetailSerializer}),
)
class ListingListCreateView(ListCreateAPIView):
    """Public catalogue (active lots by default, finished ones with `?status=ended`) and draft creation."""

    pagination_class = StandardPagination
    queryset = Listing.objects.select_related('seller', 'category').with_images()
    throttle_scope = 'listing_write'
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ListingFilter

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
class ListingDetailView(RetrieveUpdateDestroyAPIView):
    """One lot. Drafts exist only for their seller (404 for everyone else) and are the only editable state."""

    http_method_names = ('get', 'patch', 'delete', 'head', 'options')
    throttle_scope = 'listing_write'
    permission_classes = (IsAuthenticatedOrReadOnly, IsListingSeller)

    def get_serializer_class(self):
        return ListingDetailSerializer if self.request.method in SAFE_METHODS else ListingWriteSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Listing.objects.visible_to(user).select_related('seller', 'category', 'top_bid__bidder').with_images()
        )
        if user.is_authenticated:
            return queryset.annotate(
                is_watching_flag=Exists(Watch.objects.filter(user=user, listing=OuterRef('pk'))),
                has_my_bid=Exists(Bid.objects.filter(bidder=user, listing=OuterRef('pk'))),
            )
        return queryset.annotate(
            is_watching_flag=Value(False, output_field=BooleanField()),
            has_my_bid=Value(False, output_field=BooleanField()),
        )

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


class ListingSellerMixin:
    """
    Finds the listing a seller's action works on. The order of the answers matters:
    404 (a draft of somebody else), then 403 (somebody else's lot). The state is checked by the action.
    """

    permission_classes = (IsAuthenticated, IsListingSeller)

    def get_listing(self) -> Listing:
        listing = get_object_or_404(Listing.objects.visible_to(self.request.user), pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, listing)
        return listing


class DraftListingMixin(ListingSellerMixin):
    """The same, and 409 when the listing is not a draft any more (photos, publishing)."""

    not_draft_message: str | None = None

    def get_listing(self) -> Listing:
        listing = super().get_listing()
        require_draft(listing, self.not_draft_message)
        return listing


@extend_schema_view(
    post=extend_schema(
        request={'multipart/form-data': ListingImageUploadSerializer}, responses={201: ListingImageSerializer}
    )
)
class ListingImageCreateView(DraftListingMixin, GenericAPIView):
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
class ListingImageDetailView(DraftListingMixin, GenericAPIView):
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
class ListingImageOrderView(DraftListingMixin, GenericAPIView):
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


@extend_schema(request=ListingPublishSerializer, responses={200: ListingDetailSerializer})
class ListingPublishView(DraftListingMixin, GenericAPIView):
    """Puts a draft on sale. Needs at least one photo; afterwards the listing can no longer be edited."""

    serializer_class = ListingPublishSerializer
    not_draft_message = 'Only a draft can be published.'
    throttle_scope = 'listing_write'

    def post(self, request, *args, **kwargs):
        listing = self.get_listing()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = publish(listing, serializer.validated_data['duration_days'])
        return Response(ListingDetailSerializer(listing, context=self.get_serializer_context()).data)


class ListingTransitionView(ListingSellerMixin, GenericAPIView):
    """The seller's one-click state changes: runs `transition` and answers with the lot as it is afterwards."""

    serializer_class = ListingDetailSerializer
    throttle_scope = 'listing_write'

    def transition(self, listing_id: int) -> None:
        raise NotImplementedError

    def post(self, request, *args, **kwargs):
        listing = self.get_listing()
        self.transition(listing.pk)
        fresh = Listing.objects.select_related('seller', 'category', 'top_bid__bidder').with_images().get(pk=listing.pk)
        return Response(self.get_serializer(fresh).data)


@extend_schema(request=None, responses={200: ListingDetailSerializer})
class ListingCancelView(ListingTransitionView):
    """Withdraws an active lot. Only possible while nobody has bid."""

    def transition(self, listing_id: int) -> None:
        cancel(listing_id)


@extend_schema(request=None, responses={200: ListingDetailSerializer})
class ListingEndNowView(ListingTransitionView):
    """The seller accepts the current top bid and ends the auction at once. Needs at least one bid."""

    def transition(self, listing_id: int) -> None:
        end_now(listing_id)
