import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuration.settings.base')

app = Celery('configuration')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
