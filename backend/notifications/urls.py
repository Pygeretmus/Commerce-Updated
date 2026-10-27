from django.urls import path

from .views import NotificationListView, NotificationMarkReadView, NotificationUnreadCountView, WebSocketTicketView

app_name = 'notifications'

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread_count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/read/', NotificationMarkReadView.as_view(), name='notification-read'),
    path('ws/ticket/', WebSocketTicketView.as_view(), name='ws-ticket'),
]
