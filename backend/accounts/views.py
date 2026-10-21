from django.contrib.auth import get_user_model
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle

from .serializers import (
    AccountCreateSerializer,
)

User = get_user_model()


class AccountCreateView(CreateAPIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'register'
    serializer_class = AccountCreateSerializer
    permission_classes = (AllowAny,)
