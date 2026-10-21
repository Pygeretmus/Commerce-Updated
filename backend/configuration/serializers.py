from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import serializers

User = get_user_model()


class LowerEmailField(serializers.EmailField):
    def to_internal_value(self, data):
        return super().to_internal_value(data).lower()


class CustomModelSerializer(serializers.ModelSerializer):
    """
    Base serializer that automatically replaces certain model fields with
    custom serializer fields:

    - `models.EmailField` → `LowerEmailField`
    """

    serializer_field_mapping = serializers.ModelSerializer.serializer_field_mapping.copy()
    serializer_field_mapping[models.EmailField] = LowerEmailField
