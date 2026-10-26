from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'kind', 'listing', 'created_at', 'read_at')
    list_filter = ('kind',)
    raw_id_fields = ('recipient', 'listing')
