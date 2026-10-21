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
