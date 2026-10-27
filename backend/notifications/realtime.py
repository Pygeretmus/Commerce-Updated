"""
Pushes events to connected browsers through the channel layer.

Everything is sent after the database transaction commits, so nobody sees a bid that was rolled back,
and a broken channel layer (Redis down) is logged but never fails the request that triggered it.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def listing_group(listing_id: int) -> str:
    return f'listing.{listing_id}'


def _send(group: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        # 'type' names the consumer method: "push" calls Consumer.push()
        async_to_sync(layer.group_send)(group, {'type': 'push', 'payload': payload})
    except Exception:
        logger.exception('Could not push %s to %s', payload.get('type'), group)


def push(group: str, payload: dict) -> None:
    transaction.on_commit(lambda: _send(group, payload))


def push_to_listing(listing_id: int, payload: dict) -> None:
    push(listing_group(listing_id), payload)
