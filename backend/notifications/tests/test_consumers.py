from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.security.websocket import OriginValidator
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from configuration.asgi import application
from listings.models import Listing
from listings.tests.helpers import make_active_listing, make_listing
from notifications import realtime
from notifications.consumers import CLOSE_NOT_FOUND
from notifications.routing import websocket_urlpatterns

User = get_user_model()


def connect(path: str) -> WebsocketCommunicator:
    # The origin header is checked against ALLOWED_HOSTS, like a browser on the site would send it
    return WebsocketCommunicator(application, path, headers=[(b'origin', b'http://localhost')])


# Channels closes database connections after each consumer call, which would break the transaction
# a TestCase wraps around every test: so these are TransactionTestCases (they flush the tables afterwards,
# and serialized_rollback restores the categories that a migration seeds).
class ListingConsumerTest(TransactionTestCase):
    serialized_rollback = True

    async def test_it_accepts_a_viewer_of_a_public_listing_and_relays_events(self):
        # === Arrange ===
        listing = await sync_to_async(make_active_listing)(seller=None)
        viewer = connect(f'/ws/listings/{listing.pk}/')

        # === Act ===
        connected, _ = await viewer.connect()
        hello = await viewer.receive_json_from()
        await sync_to_async(realtime._send)(
            realtime.listing_group(listing.pk), {'type': 'price_update', 'current_price': '12.00'}
        )
        event = await viewer.receive_json_from()

        # === Assert ===
        self.assertTrue(connected)
        self.assertEqual(hello['type'], 'hello')
        self.assertEqual(event, {'type': 'price_update', 'current_price': '12.00'})
        await viewer.disconnect()

    async def test_it_does_not_send_events_of_other_listings(self):
        # === Arrange ===
        listing = await sync_to_async(make_active_listing)(seller=None)
        other = await sync_to_async(make_active_listing)(seller=None)
        viewer = connect(f'/ws/listings/{listing.pk}/')
        await viewer.connect()
        await viewer.receive_json_from()

        # === Act ===
        await sync_to_async(realtime._send)(realtime.listing_group(other.pk), {'type': 'price_update'})

        # === Assert ===
        self.assertTrue(await viewer.receive_nothing(timeout=0.2))
        await viewer.disconnect()

    async def test_it_closes_with_not_found_for_a_draft_and_an_unknown_listing(self):
        # === Arrange ===
        draft = await sync_to_async(make_listing)(seller=None, status=Listing.Status.DRAFT)

        for pk in (draft.pk, 999999):
            with self.subTest(listing=pk):
                viewer = connect(f'/ws/listings/{pk}/')

                # === Act ===
                await viewer.connect()
                closing = await viewer.receive_output(1)

                # === Assert === (the browser gets the code, so the client can stop retrying)
                self.assertEqual((closing['type'], closing['code']), ('websocket.close', CLOSE_NOT_FOUND))

    async def test_it_ignores_what_the_client_sends(self):
        # === Arrange ===
        listing = await sync_to_async(make_active_listing)(seller=None)
        viewer = connect(f'/ws/listings/{listing.pk}/')
        await viewer.connect()
        await viewer.receive_json_from()

        # === Act ===
        await viewer.send_json_to({'type': 'anything', 'data': 'x'})

        # === Assert === (still connected, nothing came back)
        self.assertTrue(await viewer.receive_nothing(timeout=0.2))
        await viewer.disconnect()

    async def test_it_rejects_a_browser_from_a_foreign_origin(self):
        # === Arrange ===
        listing = await sync_to_async(make_active_listing)(seller=None)
        # The project's validator reads ALLOWED_HOSTS when it is built, so use a fixed list here
        app = OriginValidator(URLRouter(websocket_urlpatterns), ['localhost'])
        evil = WebsocketCommunicator(app, f'/ws/listings/{listing.pk}/', headers=[(b'origin', b'http://evil.example')])

        # === Act ===
        connected, _ = await evil.connect()

        # === Assert ===
        self.assertFalse(connected)
