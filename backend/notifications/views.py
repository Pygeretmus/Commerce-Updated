from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from configuration.pagination import StandardPagination

from .filters import NotificationFilter
from .models import Notification
from .serializers import MarkReadSerializer, NotificationSerializer, UnreadCountSerializer


class NotificationListView(ListAPIView):
    """The newest notifications of the current user. `?unread=true` keeps only the unread ones."""

    serializer_class = NotificationSerializer
    pagination_class = StandardPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = NotificationFilter
    queryset = Notification.objects.none()  # only tells the schema generator which model this is

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related('listing')


class NotificationUnreadCountView(GenericAPIView):
    serializer_class = UnreadCountSerializer

    def get(self, request, *args, **kwargs):
        count = Notification.objects.unread_for(request.user).count()
        return Response(self.get_serializer({'count': count}).data)


class NotificationMarkReadView(GenericAPIView):
    """Marks some (`ids`) or all (`all: true`) notifications as read. Other people's ids are ignored."""

    serializer_class = MarkReadSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unread = Notification.objects.unread_for(request.user)
        if not serializer.validated_data['all']:
            unread = unread.filter(pk__in=serializer.validated_data['ids'])
        return Response(self.get_serializer({'updated': unread.update(read_at=timezone.now())}).data)
