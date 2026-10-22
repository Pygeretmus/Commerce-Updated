from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from configuration.pagination import StandardPagination

from ..models import Bid, Listing
from ..serializers import BidCreateSerializer, BidPlacedSerializer, BidSerializer
from ..services.bidding import place_bid
from ..services.state import leader_of, state_of


@extend_schema_view(
    get=extend_schema(responses=BidSerializer(many=True)),
    post=extend_schema(request=BidCreateSerializer, responses={201: BidPlacedSerializer}),
)
class BidListCreateView(ListCreateAPIView):
    """
    The bid history of a lot (highest first, other bidders masked) and placing a bid.
    A rejected bid answers 400 with a `code`: invalid_amount, auction_closed, own_listing,
    already_top_bidder or bid_too_low.
    """

    pagination_class = StandardPagination
    serializer_class = BidSerializer
    throttle_scope = 'bid'

    def get_permissions(self):
        return [AllowAny()] if self.request.method in SAFE_METHODS else [IsAuthenticated()]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method not in SAFE_METHODS:
            throttles.append(ScopedRateThrottle())
        return throttles

    def get_listing(self) -> Listing:
        return get_object_or_404(Listing.objects.visible_to(self.request.user), pk=self.kwargs['pk'])

    def get_queryset(self):
        return Bid.objects.filter(listing=self.get_listing()).select_related('bidder').order_by('-amount')

    def create(self, request, *args, **kwargs):
        listing = self.get_listing()
        serializer = BidCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bid = place_bid(listing.pk, request.user, serializer.validated_data['amount'])

        fresh = Listing.objects.select_related('top_bid__bidder').get(pk=listing.pk)
        data = {
            'bid': BidSerializer(bid, context=self.get_serializer_context()).data,
            'state': state_of(fresh, leader=leader_of(fresh)),
        }
        return Response(data, status=status.HTTP_201_CREATED)
