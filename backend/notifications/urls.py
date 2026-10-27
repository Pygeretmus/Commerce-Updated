from django.urls import path

from .views import NotificationListView, NotificationMarkReadView, NotificationUnreadCountView

app_name = 'notifications'

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread_count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/read/', NotificationMarkReadView.as_view(), name='notification-read'),
]
