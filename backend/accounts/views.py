from django.contrib.auth import get_user_model
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    AccountCreateSerializer,
    AccountSerializer,
    AccountUpdateSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'


class AccountCreateView(CreateAPIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'register'
    serializer_class = AccountCreateSerializer
    permission_classes = (AllowAny,)


class CurrentAccountView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return AccountUpdateSerializer if self.request.method != 'GET' else AccountSerializer
