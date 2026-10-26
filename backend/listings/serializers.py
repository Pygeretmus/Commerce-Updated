from decimal import Decimal
from typing import Any, ClassVar

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from configuration.serializers import CustomModelSerializer, ImageUploadField

from .constants import DURATIONS_DAYS, MIN_PRICE
from .models import Bid, Category, Comment, Listing, ListingImage
from .services.drafts import create_draft, update_draft
from .services.masking import mask_name
from .services.state import iso, leader_of


class CategorySerializer(CustomModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class CategoryBriefSerializer(CustomModelSerializer):
    class Meta:
        model = Category
        fields = ('name', 'slug')


class ListingListSerializer(CustomModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    # null when the seller deleted their account
    seller = serializers.SlugRelatedField(slug_field='username', read_only=True)
    cover = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            'id',
            'title',
            'starting_price',
            'current_price',
            'bids_count',
            'status',
            'is_ended',
            'sold',
            'published_at',
            'ends_at',
            'category',
            'seller',
            'cover',
        )

    def get_is_ended(self, obj: Listing) -> bool:
        return obj.is_ended()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_cover(self, obj: Listing) -> str | None:
        # images are prefetched in order, so this does not hit the database
        images = obj.images.all()
        if not images:
            return None
        # The small preview when it is ready, the original photo before that
        file = images[0].thumbnail or images[0].image
        request = self.context.get('request')
        return request.build_absolute_uri(file.url) if request else file.url


class ListingImageSerializer(CustomModelSerializer):
    url = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = ListingImage
        fields = ('id', 'url', 'thumbnail', 'position')

    def _absolute(self, file) -> str:
        request = self.context.get('request')
        return request.build_absolute_uri(file.url) if request else file.url

    def get_url(self, obj: ListingImage) -> str:
        return self._absolute(obj.image)

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_thumbnail(self, obj: ListingImage) -> str | None:
        # null until the background task has made the preview
        return self._absolute(obj.thumbnail) if obj.thumbnail else None


def bid_status(listing: Listing, user_id: int | None) -> str:
    """What a bid on this lot means for a bidder: winning/outbid while it runs, won/lost afterwards."""
    leading = listing.top_bid is not None and listing.top_bid.bidder_id == user_id
    if listing.status == Listing.Status.ACTIVE:
        return 'winning' if leading else 'outbid'
    return 'won' if listing.sold and leading else 'lost'


class ListingDetailSerializer(CustomModelSerializer):
    """
    One lot. The queryset should select_related seller, category and top_bid__bidder, and may annotate
    `is_watching_flag` and `has_my_bid` (Exists) to keep the answer at a fixed number of queries.
    """

    category = CategoryBriefSerializer(read_only=True)
    seller = serializers.SlugRelatedField(slug_field='username', read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    has_reserve = serializers.SerializerMethodField()
    reserve_met = serializers.SerializerMethodField()
    next_min_bid = serializers.SerializerMethodField()
    leader = serializers.SerializerMethodField()
    winner = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()
    seconds_left = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()
    is_seller = serializers.SerializerMethodField()
    is_watching = serializers.SerializerMethodField()
    my_bid_status = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            'id',
            'title',
            'description',
            'starting_price',
            'reserve_price',
            'has_reserve',
            'reserve_met',
            'current_price',
            'bids_count',
            'next_min_bid',
            'leader',
            'winner',
            'status',
            'is_ended',
            'sold',
            'published_at',
            'ends_at',
            'closed_at',
            'seconds_left',
            'server_time',
            'created_at',
            'category',
            'seller',
            'images',
            'is_seller',
            'is_watching',
            'my_bid_status',
        )

    def _user_id(self) -> int | None:
        request = self.context.get('request')
        return request.user.pk if request and request.user.is_authenticated else None

    def get_has_reserve(self, obj: Listing) -> bool:
        return obj.reserve_price is not None

    def get_reserve_met(self, obj: Listing) -> bool | None:
        # Bidders learn whether the secret reserve was reached, never what it is
        return obj.reserve_met if obj.reserve_price is not None else None

    def get_next_min_bid(self, obj: Listing) -> str:
        return f'{obj.next_min_bid:.2f}'

    def get_leader(self, obj: Listing) -> str | None:
        return leader_of(obj)

    def get_winner(self, obj: Listing) -> str | None:
        return leader_of(obj) if obj.sold else None

    def get_is_ended(self, obj: Listing) -> bool:
        return obj.is_ended()

    def get_seconds_left(self, obj: Listing) -> int | None:
        if obj.status != Listing.Status.ACTIVE or obj.ends_at is None:
            return None
        return max(0, int((obj.ends_at - timezone.now()).total_seconds()))

    def get_server_time(self, obj: Listing) -> str:
        return iso(timezone.now())

    def get_is_seller(self, obj: Listing) -> bool:
        return self._user_id() is not None and obj.seller_id == self._user_id()

    def get_is_watching(self, obj: Listing) -> bool:
        return bool(getattr(obj, 'is_watching_flag', False))

    @extend_schema_field(serializers.ChoiceField(choices=['winning', 'outbid', 'won', 'lost'], allow_null=True))
    def get_my_bid_status(self, obj: Listing) -> str | None:
        if not getattr(obj, 'has_my_bid', False):
            return None
        return bid_status(obj, self._user_id())

    def to_representation(self, instance: Listing):
        data = super().to_representation(instance)
        if not self.get_is_seller(instance):
            # The reserve is a secret: bidders only learn that one exists
            data.pop('reserve_price')
        return data


class ListingWriteSerializer(CustomModelSerializer):
    """Input for creating and editing a draft. Status, seller and dates are not writable."""

    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Listing
        fields = ('title', 'description', 'starting_price', 'reserve_price', 'category')
        extra_kwargs: ClassVar[dict[str, dict[str, Any]]] = {
            'title': {'min_length': 3},
            'description': {'max_length': 5000},
            'starting_price': {'min_value': MIN_PRICE},
            'reserve_price': {'min_value': MIN_PRICE, 'required': False, 'allow_null': True},
        }

    def validate(self, attrs: dict) -> dict:
        # On PATCH the missing field comes from the stored listing, not from the request
        current = self.instance
        starting = attrs.get('starting_price', current.starting_price if current else None)
        reserve = attrs.get('reserve_price', current.reserve_price if current else None)
        if starting is not None and reserve is not None and reserve < starting:
            raise serializers.ValidationError(
                {'reserve_price': 'Reserve price cannot be lower than the starting price.'},
                code='reserve_below_starting_price',
            )
        return attrs

    def create(self, validated_data: dict) -> Listing:
        return create_draft(self.context['request'].user, **validated_data)

    def update(self, instance: Listing, validated_data: dict) -> Listing:
        return update_draft(instance, **validated_data)


class ListingImageUploadSerializer(serializers.Serializer):
    image = ImageUploadField(help_text='JPEG, PNG or WEBP, up to 5 MB')


class ListingImageOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class ListingPublishSerializer(serializers.Serializer):
    duration_days = serializers.ChoiceField(choices=DURATIONS_DAYS, help_text='How long the auction runs')


class ListingStateSerializer(serializers.Serializer):
    """Price, leader and end time: the part of a lot that changes while people bid."""

    current_price = serializers.CharField()
    bids_count = serializers.IntegerField()
    next_min_bid = serializers.CharField()
    ends_at = serializers.DateTimeField(allow_null=True)
    leader = serializers.CharField(allow_null=True)
    server_time = serializers.DateTimeField()


class BidSerializer(serializers.ModelSerializer):
    """A bid in the public history: other people appear masked, my own bids carry my real name."""

    bidder = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Bid
        fields = ('id', 'bidder', 'amount', 'created_at', 'is_mine')

    def _user_id(self) -> int | None:
        request = self.context.get('request')
        return request.user.pk if request and request.user.is_authenticated else None

    def get_is_mine(self, obj: Bid) -> bool:
        return obj.bidder_id is not None and obj.bidder_id == self._user_id()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_bidder(self, obj: Bid) -> str | None:
        if obj.bidder is None:
            return None
        return obj.bidder.username if self.get_is_mine(obj) else mask_name(obj.bidder.username)


class BidCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))


class BidPlacedSerializer(serializers.Serializer):
    bid = BidSerializer()
    state = ListingStateSerializer()


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=1000, trim_whitespace=True)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(slug_field='username', read_only=True)
    is_seller = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ('id', 'author', 'body', 'created_at', 'is_seller', 'is_mine')

    def get_is_seller(self, obj: Comment) -> bool:
        return obj.author_id is not None and obj.author_id == self.context['listing'].seller_id

    def get_is_mine(self, obj: Comment) -> bool:
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.author_id == request.user.pk)
