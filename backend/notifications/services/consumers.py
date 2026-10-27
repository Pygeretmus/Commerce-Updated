from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .realtime import listing_group, user_group
from .tickets import consume_ticket

# Close codes in the private range (4000-4999)
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404


class PushConsumer(AsyncJsonWebsocketConsumer):
    """Base class: joins one group and relays every pushed event to the browser. Browsers send nothing."""

    group: str | None = None

    async def join(self, group: str) -> None:
        self.group = group
        await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'hello', 'server_time': timezone.now().isoformat()})

    async def refuse(self, code: int) -> None:
        """
        Closes with an application code. It is sent after accept() on purpose: a socket closed before that is
        answered with a bare HTTP 403, and the browser reports 1006 for it, the same as for a network error.
        """
        await self.accept()
        await self.close(code=code)

    async def disconnect(self, code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Read-only channel: anything the client sends is ignored
        return

    async def push(self, event):
        await self.send_json(event['payload'])


class ListingConsumer(PushConsumer):
    """Public price updates of one lot: `/ws/listings/<id>/`."""

    async def connect(self):
        from listings.models import Listing

        listing_id = self.scope['url_route']['kwargs']['listing_id']
        exists = await Listing.objects.exclude(status=Listing.Status.DRAFT).filter(pk=listing_id).aexists()
        if not exists:
            await self.refuse(CLOSE_NOT_FOUND)
            return
        await self.join(listing_group(listing_id))


class UserConsumer(PushConsumer):
    """Personal events (notifications): `/ws/me/?ticket=...`."""

    async def connect(self):
        query = parse_qs(self.scope['query_string'].decode())
        ticket = query.get('ticket', [''])[0]
        user_id = await sync_to_async(consume_ticket)(ticket)  # a cache call, not a database one
        if user_id is None:
            await self.refuse(CLOSE_UNAUTHORIZED)
            return
        await self.join(user_group(user_id))
