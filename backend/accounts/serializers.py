from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from configuration.serializers import CustomModelSerializer

User = get_user_model()


class AccountCreateSerializer(CustomModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password], max_length=255)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')

    def create(self, validated_data: dict):
        return User.objects.create_user(**validated_data)


class CheckCurrentPasswordMixin:
    def _require_current_password(self, instance: User, validated_data: dict) -> None:
        current_password = validated_data.pop('current_password', None)

        if current_password is None:
            # Additional check required for PATCH method that ignores required=True
            raise serializers.ValidationError({'current_password': 'This field is required.'}, code='required')
        if not instance.check_password(current_password):
            raise serializers.ValidationError({'current_password': 'Incorrect current password'}, code='invalid')


class AccountSerializer(CustomModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')


class AccountUpdateSerializer(CheckCurrentPasswordMixin, CustomModelSerializer):
    current_password = serializers.CharField(write_only=True, max_length=255)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'current_password')

    def update(self, instance: User, validated_data: dict):
        self._require_current_password(instance, validated_data)
        return super().update(instance, validated_data)


class AccountPasswordChangeSerializer(CheckCurrentPasswordMixin, CustomModelSerializer):
    current_password = serializers.CharField(write_only=True, max_length=255)
    new_password = serializers.CharField(write_only=True, max_length=255)

    class Meta:
        model = User
        fields = ('new_password', 'current_password')

    def validate_new_password(self, value: str) -> str:
        validate_password(value, user=self.instance)
        return value

    def update(self, instance: User, validated_data: dict):
        self._require_current_password(instance, validated_data)
        instance.set_password(validated_data['new_password'])
        instance.save(update_fields=['password'])
        return instance
