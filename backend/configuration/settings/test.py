import os

for key, value in {
    'SECRET_KEY': 'test-secret-key',
    'ALLOWED_HOSTS': 'testserver,localhost',
    'CSRF_TRUSTED_ORIGINS': 'http://localhost,',
    'CORS_ALLOWED_ORIGINS': 'http://localhost,',
    'REDIS_URL': 'redis://localhost:6379/0',
}.items():
    os.environ.setdefault(key, value)

from .base import *

REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {name: '10000/min' for name in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    },
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
