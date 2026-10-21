#!/usr/bin/env bash

set -o errexit

echo "Creating superuser..."

python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if email and password and not User.objects.filter(email__iexact=email).exists():
    User.objects.create_superuser(username, email, password)
    print('Superuser created.')
else:
    print('Superuser already exists, skipping.')
"

echo "Collecting static files..."

python manage.py collectstatic --noinput

echo "Starting web server..."

exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 8 \
    --timeout 30 \
    configuration.wsgi:application
