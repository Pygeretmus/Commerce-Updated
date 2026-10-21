from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from configuration.serializers import CustomModelSerializer

from .models import Category, Listing, ListingImage
from .state import iso


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

    class Meta:
        model = Listing
        fields = (
            'id',
            'title',
            'starting_price',
            'current_price',
            'status',
            'published_at',
            'ends_at',
            'category',
            'seller',
            'cover',
        )

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


class ListingDetailSerializer(CustomModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    seller = serializers.SlugRelatedField(slug_field='username', read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    has_reserve = serializers.SerializerMethodField()
    seconds_left = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()
    is_seller = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            'id',
            'title',
            'description',
            'starting_price',
            'reserve_price',
            'has_reserve',
            'current_price',
            'status',
            'published_at',
            'ends_at',
            'seconds_left',
            'server_time',
            'created_at',
            'category',
            'seller',
            'images',
            'is_seller',
        )

    def _user_id(self) -> int | None:
        request = self.context.get('request')
        return request.user.pk if request and request.user.is_authenticated else None

    def get_has_reserve(self, obj: Listing) -> bool:
        return obj.reserve_price is not None

    def get_seconds_left(self, obj: Listing) -> int | None:
        if obj.status != Listing.Status.ACTIVE or obj.ends_at is None:
            return None
        return max(0, int((obj.ends_at - timezone.now()).total_seconds()))

    def get_server_time(self, obj: Listing) -> str:
        return iso(timezone.now())

    def get_is_seller(self, obj: Listing) -> bool:
        return self._user_id() is not None and obj.seller_id == self._user_id()

    def to_representation(self, instance: Listing):
        data = super().to_representation(instance)
        if not self.get_is_seller(instance):
            # The reserve is a secret: bidders only learn that one exists
            data.pop('reserve_price')
        return data
