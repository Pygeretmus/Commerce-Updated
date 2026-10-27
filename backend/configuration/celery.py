import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuration.settings.base')

app = Celery('configuration')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'close-expired-listings-every-30-seconds': {
        'task': 'listings.tasks.close_expired_listings',
        'schedule': 30,
    },
    'notify-ending-soon-every-5-minutes': {
        'task': 'notifications.tasks.notify_ending_soon',
        'schedule': 300,
    },
}
