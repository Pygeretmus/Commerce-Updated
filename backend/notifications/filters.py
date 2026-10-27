from django_filters.rest_framework import BooleanFilter, FilterSet

from .models import Notification


class NotificationFilter(FilterSet):
    unread = BooleanFilter(method='filter_unread', help_text='Only unread notifications')

    class Meta:
        model = Notification
        fields = ()  # every filter is declared above

    def filter_unread(self, queryset, name, value):
        return queryset.filter(read_at__isnull=True) if value else queryset
