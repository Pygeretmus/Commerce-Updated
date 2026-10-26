from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Category, Listing, Watch
from .helpers import bid_on, make_active_listing

User = get_user_model()


class APIListingListFiltersTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User, username='seller')
        cls.me = G(User)

    def setUp(self):
        self.url = reverse('listings:listing-list')

    def ids(self, query: str = '') -> list[int]:
        response = self.client.get(self.url + query)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return [row['id'] for row in response.json()['results']]

    def lot(self, **kwargs) -> Listing:
        return make_active_listing(seller=kwargs.pop('seller', self.seller), **kwargs)

    # --- search ----------------------------------------------------------------------

    def test_it_finds_lots_by_a_word_in_the_title_or_the_description(self):
        # === Arrange ===
        vase = self.lot(title='Blue vase', description='Glazed ceramic')
        clock = self.lot(title='Old clock', description='A ceramic base and brass hands')
        self.lot(title='Lamp', description='Nothing relevant')

        # === Act & Assert ===
        self.assertCountEqual(self.ids('?q=ceramic'), [vase.pk, clock.pk])
        self.assertEqual(self.ids('?q=vase'), [vase.pk])

    def test_it_requires_all_words_of_the_query(self):
        # === Arrange ===
        both = self.lot(title='Blue vase', description='Glazed')
        self.lot(title='Blue lamp', description='Glazed')

        # === Act & Assert ===
        self.assertEqual(self.ids('?q=blue vase'), [both.pk])

    def test_it_ignores_letter_case(self):
        # === Arrange ===
        vase = self.lot(title='Blue VASE')

        # === Act & Assert ===
        self.assertEqual(self.ids('?q=vase'), [vase.pk])

    @skipUnless(connection.vendor == 'postgresql', 'needs PostgreSQL')
    def test_it_finds_word_forms_with_full_text_search(self):
        # === Arrange ===
        watch = self.lot(title='Pocket watch', description='Runs well')

        # === Act & Assert === ("watches" is stemmed to "watch")
        self.assertEqual(self.ids('?q=watches'), [watch.pk])

    def test_it_does_not_treat_the_query_as_a_pattern(self):
        # === Arrange ===
        self.lot(title='Plain')

        # === Act & Assert ===
        self.assertEqual(self.ids('?q=%25'), [])

    # --- filters ---------------------------------------------------------------------

    def test_it_filters_by_category_and_seller(self):
        # === Arrange ===
        art = self.lot()
        other_category = Category.objects.exclude(slug='art').first()
        self.lot(category=other_category)
        other_seller = self.lot(seller=self.me)

        # === Act & Assert ===
        self.assertIn(art.pk, self.ids('?category=art'))
        self.assertEqual(len(self.ids(f'?category={other_category.slug}&seller=seller')), 1)
        self.assertEqual(self.ids(f'?seller={self.me.username}'), [other_seller.pk])

    def test_it_filters_by_the_current_price_not_the_starting_price(self):
        # === Arrange ===
        cheap = self.lot(starting_price=Decimal(10))
        pricey = self.lot(starting_price=Decimal(10))
        bid_on(pricey, self.me, '80.00')

        # === Act & Assert ===
        self.assertEqual(self.ids('?min_price=50'), [pricey.pk])
        self.assertEqual(self.ids('?max_price=50'), [cheap.pk])
        self.assertCountEqual(self.ids('?min_price=10&max_price=80'), [cheap.pk, pricey.pk])

    def test_it_rejects_an_inverted_price_range_and_bad_numbers(self):
        for query in ('?min_price=50&max_price=10', '?min_price=abc', '?min_price=-1'):
            with self.subTest(query=query):
                # === Act ===
                response = self.client.get(self.url + query)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- ordering --------------------------------------------------------------------

    def test_it_orders_the_list(self):
        # === Arrange ===
        now = timezone.now()
        a = self.lot(starting_price=Decimal(30), ends_at=now + timedelta(days=3), published_at=now - timedelta(hours=3))
        b = self.lot(starting_price=Decimal(10), ends_at=now + timedelta(days=1), published_at=now - timedelta(hours=2))
        c = self.lot(starting_price=Decimal(20), ends_at=now + timedelta(days=2), published_at=now - timedelta(hours=1))
        bid_on(a, self.me, '30.00')

        # === Act & Assert ===
        self.assertEqual(self.ids('?ordering=newest'), [c.pk, b.pk, a.pk])
        self.assertEqual(self.ids('?ordering=ending_soon'), [b.pk, c.pk, a.pk])
        self.assertEqual(self.ids('?ordering=price_asc'), [b.pk, c.pk, a.pk])
        self.assertEqual(self.ids('?ordering=price_desc'), [a.pk, c.pk, b.pk])
        self.assertEqual(self.ids('?ordering=most_bids')[0], a.pk)

    def test_it_rejects_an_unknown_ordering(self):
        # === Act ===
        response = self.client.get(self.url + '?ordering=random')

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['param'], 'ordering')

    # --- personal lists --------------------------------------------------------------

    def test_it_lists_my_watchlist_in_every_status(self):
        # === Arrange ===
        watched = self.lot()
        ended = self.lot(status=Listing.Status.ENDED)
        self.lot()
        for listing in (watched, ended):
            Watch.objects.create(user=self.me, listing=listing)
        self.client.force_authenticate(self.me)

        # === Act & Assert ===
        self.assertCountEqual(self.ids('?watching=true'), [watched.pk, ended.pk])
        self.assertEqual(self.ids('?watching=true&status=ended'), [ended.pk])

    def test_it_lists_the_lots_I_bid_on(self):
        # === Arrange ===
        mine = self.lot(starting_price=Decimal(10))
        self.lot(starting_price=Decimal(10))
        bid_on(mine, self.me, '10.00')
        self.client.force_authenticate(self.me)

        # === Act & Assert ===
        self.assertEqual(self.ids('?bidding=true'), [mine.pk])

    def test_it_needs_a_login_for_personal_filters(self):
        for query in ('?watching=true', '?bidding=true'):
            with self.subTest(query=query):
                # === Act ===
                response = self.client.get(self.url + query)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_it_uses_a_fixed_number_of_queries_with_filters(self):
        # === Arrange ===
        for index in range(8):
            self.lot(title=f'Vase {index}')

        # === Act & Assert === (count, rows, images)
        with self.assertNumQueries(3):
            self.client.get(self.url + '?q=vase&ordering=price_asc&min_price=1')
