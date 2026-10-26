from collections import Counter

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from configuration.pagination import StandardPagination

from ..constants import BID_STATUSES
from ..filters import MyBidFilter, MyListingFilter
from ..models import Listing, Watch
from ..serializers import MeSummarySerializer, MyBidSerializer, MyListingSerializer


class MyBidsView(ListAPIView):
    """Lots I have bid on, newest bid first. Filter with `?status=winning|outbid|won|lost`."""

    serializer_class = MyBidSerializer
    pagination_class = StandardPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = MyBidFilter
    queryset = Listing.objects.none()  # only tells the schema generator which model this is

    def get_queryset(self):
        return Listing.objects.bid_on_by(self.request.user).order_by('-last_bid_at', '-id')


class MyListingsView(ListAPIView):
    """My own lots, drafts included, newest first. Filter with `?status=`."""

    serializer_class = MyListingSerializer
    pagination_class = StandardPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = MyListingFilter
    queryset = Listing.objects.none()  # only tells the schema generator which model this is

    def get_queryset(self):
        return (
            Listing.objects.filter(seller=self.request.user)
            .select_related('seller', 'category', 'top_bid__bidder')
            .with_images()
            .order_by('-created_at', '-id')
        )


class MySummaryView(GenericAPIView):
    """Every counter the navigation needs (tab badges, the bell), in a handful of cheap queries."""

    serializer_class = MeSummarySerializer

    def get(self, request, *args, **kwargs):
        user = request.user

        bids = dict.fromkeys(BID_STATUSES, 0)
        bids.update(Counter(Listing.objects.bid_on_by(user).order_by().values_list('my_status', flat=True)))

        by_status = dict(Listing.objects.filter(seller=user).order_by().values_list('status').annotate(n=Count('pk')))
        listings = {status: by_status.get(status, 0) for status in Listing.Status.values}

        return Response(
            self.get_serializer(
                {
                    'bids': bids,
                    'listings': listings,
                    'watching': Watch.objects.filter(user=user).count(),
                }
            ).data
        )
