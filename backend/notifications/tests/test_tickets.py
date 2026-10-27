from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase

from ..services.tickets import consume_ticket, issue_ticket


class TicketsTest(SimpleTestCase):
    def setUp(self):
        self.addCleanup(cache.clear)

    def test_it_gives_the_user_id_back_exactly_once(self):
        # === Arrange ===
        ticket = issue_ticket(42)

        # === Act ===
        first, second = consume_ticket(ticket), consume_ticket(ticket)

        # === Assert ===
        self.assertEqual((first, second), (42, None))

    def test_it_issues_a_different_ticket_every_time(self):
        # === Act & Assert ===
        self.assertNotEqual(issue_ticket(1), issue_ticket(1))

    def test_it_refuses_empty_and_unknown_tickets(self):
        # === Act & Assert ===
        self.assertIsNone(consume_ticket(''))
        self.assertIsNone(consume_ticket('made-up'))

    def test_it_stores_the_ticket_for_a_short_time_only(self):
        # === Arrange ===
        from unittest import mock

        # === Act ===
        with mock.patch('notifications.services.tickets.cache') as fake_cache:
            issue_ticket(7)

        # === Assert ===
        self.assertEqual(fake_cache.set.call_args.args[2], settings.TICKET_TTL)
