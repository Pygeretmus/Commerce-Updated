"""
ASGI config for commerce project.

HTTP goes to Django, WebSocket connections go to the Channels consumers (live prices and notifications).
Run it with an ASGI server, for example: uvicorn configuration.asgi:application
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuration.settings.base')

# Django must be set up before the consumers (and their models) are imported
django_asgi_app = get_asgi_application()

from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        # Browsers must come from an allowed host: a page on another site cannot open the socket
        'websocket': AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
    }
)
