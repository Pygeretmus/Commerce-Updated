"""
One-use tickets for opening a WebSocket. A JWT in the URL of a WebSocket would end up in proxy and
server logs, so the client asks the API for a random ticket (valid for seconds, usable once) and
puts that in the URL instead.
"""

import secrets

from django.conf import settings
from django.core.cache import cache


def _key(ticket: str) -> str:
    return f'ws-ticket:{ticket}'


def issue_ticket(user_id: int) -> str:
    ticket = secrets.token_urlsafe(32)
    cache.set(_key(ticket), user_id, settings.TICKET_TTL)
    return ticket


def consume_ticket(ticket: str) -> int | None:
    """Returns the user id, or None when the ticket is unknown, expired or already used."""
    if not ticket:
        return None
    user_id = cache.get(_key(ticket))
    # delete() reports whether the key was still there: of two parallel connections only one gets True
    if user_id is None or not cache.delete(_key(ticket)):
        return None
    return user_id
