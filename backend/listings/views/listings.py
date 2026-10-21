from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
)
from rest_framework.permissions import AllowAny

from configuration.pagination import StandardPagination

from ..models import Category, Listing
from ..serializers import (
    CategorySerializer,
    ListingDetailSerializer,
    ListingListSerializer,
)


class CategoryListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    pagination_class = None


class ListingListView(ListAPIView):
    pagination_class = StandardPagination
    queryset = Listing.objects.select_related('seller', 'category').with_images()
    serializer_class = ListingListSerializer
    permission_classes = (AllowAny,)


class ListingDetailView(RetrieveAPIView):
    serializer_class = ListingDetailSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        user = self.request.user
        return Listing.objects.visible_to(user).select_related('seller', 'category').with_images()
