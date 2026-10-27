from rest_framework import serializers

from .services.texts import render_text


class NotificationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    text = serializers.SerializerMethodField()
    listing = serializers.SerializerMethodField()
    data = serializers.JSONField()
    created_at = serializers.DateTimeField()
    read_at = serializers.DateTimeField(allow_null=True)

    def get_text(self, obj) -> str:
        return render_text(obj.kind, obj.listing.title, obj.data)

    def get_listing(self, obj) -> dict:
        return {'id': obj.listing_id, 'title': obj.listing.title}


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True, max_length=200)
    all = serializers.BooleanField(required=False, default=False, write_only=True)
    updated = serializers.IntegerField(read_only=True)

    def validate(self, attrs: dict) -> dict | None:
        if not attrs.get('all') and not attrs.get('ids'):
            raise serializers.ValidationError('Pass "ids" or "all": true.', code='nothing_to_mark')
        return attrs


class WebSocketTicketSerializer(serializers.Serializer):
    ticket = serializers.CharField()
    expires_in = serializers.IntegerField(help_text='Seconds the ticket stays valid.')
