from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase

from listings.tests.helpers import make_active_listing, make_listing, make_listing_image

User = get_user_model()


class APIListingImageOrderViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.seller)
        self.listing = make_listing(seller=self.seller)
        self.photos = [make_listing_image(self.listing, position) for position in range(3)]
        self.url = self.url_for(self.listing)

    def url_for(self, listing) -> str:
        return reverse('listings:listing-image-order', args=[listing.pk])

    def positions(self) -> list[int]:
        """Ids of the photos in the order the listing shows them."""
        return list(self.listing.images.values_list('pk', flat=True))

    def test_it_reorders_photos(self):
        # === Arrange ===
        first, second, third = (photo.pk for photo in self.photos)

        # === Act ===
        response = self.client.put(self.url, data={'ids': [third, first, second]})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([photo['id'] for photo in response.json()], [third, first, second])
        self.assertEqual([photo['position'] for photo in response.json()], [0, 1, 2])
        self.assertEqual(self.positions(), [third, first, second])

    def test_it_closes_gaps_in_positions(self):
        # === Arrange ===
        self.photos[1].delete()
        first, third = self.photos[0].pk, self.photos[2].pk

        # === Act ===
        response = self.client.put(self.url, data={'ids': [third, first]})

        # === Assert ===
        self.assertEqual([photo['position'] for photo in response.json()], [0, 1])

    def test_it_accepts_empty_list_for_listing_without_photos(self):
        # === Arrange ===
        empty = make_listing(seller=self.seller)

        # === Act ===
        response = self.client.put(self.url_for(empty), data={'ids': []})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_it_returns_error_if_a_photo_is_missing(self):
        # === Arrange ===
        before = self.positions()

        # === Act ===
        response = self.client.put(self.url, data={'ids': before[:2]})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'invalid_order')
        self.assertEqual(self.positions(), before)

    def test_it_returns_error_if_an_id_is_extra_or_unknown(self):
        # === Arrange ===
        before = self.positions()

        # === Act ===
        response = self.client.put(self.url, data={'ids': [*before, 999999]})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors'][0]['code'], 'invalid_order')
        self.assertEqual(self.positions(), before)

    def test_it_returns_error_if_a_photo_of_another_listing_is_listed(self):
        # === Arrange ===
        before = self.positions()
        foreign = make_listing_image(make_listing(seller=self.seller))

        # === Act ===
        response = self.client.put(self.url, data={'ids': [*before[:2], foreign.pk]})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.positions(), before)

    def test_it_returns_error_if_an_id_is_repeated(self):
        # === Arrange ===
        before = self.positions()

        # === Act ===
        response = self.client.put(self.url, data={'ids': [before[0], before[0], before[1], before[2]]})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.positions(), before)

    def test_it_returns_error_if_ids_are_missing_or_not_numbers(self):
        for data in ({}, {'ids': 'abc'}, {'ids': ['x']}):
            with self.subTest(data=data):
                # === Act ===
                response = self.client.put(self.url, data=data)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_returns_conflict_if_listing_is_not_a_draft(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.seller)

        # === Act ===
        response = self.client.put(self.url_for(listing), data={'ids': []})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_it_returns_forbidden_for_other_users_published_listing(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.other)

        # === Act ===
        response = self.client.put(self.url_for(listing), data={'ids': []})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_it_returns_not_found_for_other_users_draft(self):
        # === Arrange ===
        listing = make_listing(seller=self.other)

        # === Act ===
        response = self.client.put(self.url_for(listing), data={'ids': []})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.client.put(self.url, data={'ids': self.positions()})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
