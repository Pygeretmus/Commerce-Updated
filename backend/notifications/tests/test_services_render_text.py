from django.test import TestCase

from ..models import Notification
from ..services.texts import render_text


class RenderTextTest(TestCase):
    def test_it_renders_every_kind(self):
        # === Arrange ===
        data = {'amount': '12.00', 'author': 'alice', 'sold': True}

        # === Act & Assert ===
        for kind in Notification.Kind.values:
            with self.subTest(kind=kind):
                text = render_text(kind, 'Blue vase', data)
                self.assertIn('Blue vase', text)

    def test_it_puts_the_amount_into_the_text(self):
        # === Act & Assert ===
        self.assertEqual(
            render_text('outbid', 'Vase', {'amount': '12.00'}), 'You were outbid on "Vase". The price is now $12.00.'
        )
        self.assertEqual(render_text('won', 'Vase', {'amount': '12.00'}), 'You won "Vase" for $12.00.')

    def test_it_distinguishes_a_sale_from_no_sale(self):
        # === Act & Assert ===
        self.assertEqual(render_text('listing_ended', 'Vase', {'sold': True}), '"Vase" has ended.')
        self.assertEqual(render_text('listing_ended', 'Vase', {'sold': False}), '"Vase" has ended without a sale.')
