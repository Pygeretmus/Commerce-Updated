from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from configuration.pagination import StandardPagination

from .filters import NotificationFilter
from .models import Notification
from .serializers import MarkReadSerializer, NotificationSerializer, UnreadCountSerializer


@extend_schema(parameters=[OpenApiParameter('unread', bool, description='Only unread notifications')])
class NotificationListView(ListAPIView):
    """The newest notifications of the current user."""

    serializer_class = NotificationSerializer
    pagination_class = StandardPagination
    filterset_class = NotificationFilter

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user).select_related('listing')
        if self.request.query_params.get('unread', '').lower() in ('1', 'true'):
            queryset = queryset.filter(read_at__isnull=True)
        return queryset


class NotificationUnreadCountView(GenericAPIView):
    serializer_class = UnreadCountSerializer

    def get(self, request, *args, **kwargs):
        count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        return Response(self.get_serializer({'count': count}).data)


class NotificationMarkReadView(GenericAPIView):
    """Marks some (`ids`) or all (`all: true`) notifications as read. Other people's ids are ignored."""

    serializer_class = MarkReadSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unread = Notification.objects.filter(recipient=request.user, read_at__isnull=True)
        if not serializer.validated_data['all']:
            unread = unread.filter(pk__in=serializer.validated_data['ids'])
        return Response(self.get_serializer({'updated': unread.update(read_at=timezone.now())}).data)
