from datetime import UTC, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from ..constants import DURATIONS_DAYS
from ..models import Listing
from .helpers import make_active_listing, make_image_file, make_listing, make_listing_image

User = get_user_model()

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


class APIListingPublishViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = G(User)
        cls.other = G(User)

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.seller)
        self.listing = make_listing(seller=self.seller, starting_price=10, reserve_price=50)
        make_listing_image(self.listing)
        self.url = self.url_for(self.listing)

    def url_for(self, listing) -> str:
        return reverse('listings:listing-publish', args=[listing.pk])

    def publish(self, duration_days=7, url=None):
        with mock.patch('listings.services.drafts.timezone.now', return_value=NOW):
            return self.client.post(url or self.url, data={'duration_days': duration_days})

    def test_it_publishes_draft(self):
        # === Act ===
        response = self.publish(7)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'active')
        self.assertEqual(self.listing.published_at, NOW)
        self.assertEqual(self.listing.ends_at, NOW + timedelta(days=7))
        self.assertIsNone(self.listing.closed_at)

    def test_it_returns_detail_of_the_published_listing(self):
        # === Act ===
        response = self.publish(3)

        # === Assert ===
        data = response.json()
        self.assertEqual(data['id'], self.listing.pk)
        self.assertEqual(data['status'], 'active')
        self.assertEqual(data['published_at'], '2026-10-19T12:00:00Z')
        self.assertEqual(data['ends_at'], '2026-10-22T12:00:00Z')
        self.assertEqual(data['reserve_price'], '50.00')
        self.assertEqual(len(data['images']), 1)

    def test_it_ends_the_auction_after_the_chosen_number_of_days(self):
        for days in DURATIONS_DAYS:
            with self.subTest(days=days):
                # === Arrange ===
                listing = make_listing(seller=self.seller)
                make_listing_image(listing)

                # === Act ===
                response = self.publish(days, self.url_for(listing))

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                listing.refresh_from_db()
                self.assertEqual(listing.ends_at, NOW + timedelta(days=days))

    def test_it_accepts_duration_sent_as_text(self):
        # === Act === (form data and query strings carry numbers as text)
        response = self.client.post(self.url, data={'duration_days': '5'}, format='multipart')

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_it_shows_the_listing_in_the_public_catalogue(self):
        # === Arrange ===
        self.client.logout()
        self.assertEqual(self.client.get(reverse('listings:listing-list')).json()['count'], 0)
        self.client.force_authenticate(user=self.seller)

        # === Act ===
        self.client.post(self.url, data={'duration_days': 7})

        # === Assert ===
        self.client.logout()
        results = self.client.get(reverse('listings:listing-list')).json()['results']
        self.assertEqual([r['id'] for r in results], [self.listing.pk])
        self.assertIsNotNone(results[0]['cover'])
        self.assertIsNotNone(results[0]['ends_at'])

    def test_it_ignores_other_fields_sent_by_client(self):
        # === Act ===
        with mock.patch('listings.services.drafts.timezone.now', return_value=NOW):
            response = self.client.post(
                self.url,
                data={
                    'duration_days': 1,
                    'status': 'ended',
                    'ends_at': '2030-01-01T00:00:00Z',
                    'seller': self.other.pk,
                },
            )

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'active')
        self.assertEqual(self.listing.ends_at, NOW + timedelta(days=1))
        self.assertEqual(self.listing.seller, self.seller)

    def test_it_returns_error_if_duration_is_not_allowed(self):
        for value in (0, 2, 4, 15, 30, -1, 'abc', None, 7.5):
            with self.subTest(value=value):
                # === Act ===
                response = self.publish(value)

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                errors = response.json()['errors']
                self.assertEqual([e['param'] for e in errors], ['duration_days'])
                self.listing.refresh_from_db()
                self.assertEqual(self.listing.status, 'draft')
                self.assertIsNone(self.listing.ends_at)

    def test_it_returns_error_if_duration_is_missing(self):
        # === Act ===
        response = self.client.post(self.url, data={})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'status': 400,
                'errors': [{'param': 'duration_days', 'message': 'This field is required.', 'code': 'required'}],
            },
        )

    def test_it_returns_error_if_listing_has_no_photos(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller)

        # === Act ===
        response = self.publish(7, self.url_for(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                'status': 400,
                'errors': [
                    {'param': None, 'message': 'Add at least one photo before publishing.', 'code': 'no_photos'}
                ],
            },
        )
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'draft')

    def test_it_does_not_count_photos_of_other_listings(self):
        # === Arrange ===
        listing = make_listing(seller=self.seller)

        # === Act === (self.listing has a photo, this one has none)
        response = self.publish(7, self.url_for(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_returns_conflict_if_listing_is_not_a_draft(self):
        for value in (Listing.Status.ACTIVE, Listing.Status.ENDED, Listing.Status.CANCELLED):
            with self.subTest(status=value):
                # === Arrange ===
                listing = make_active_listing(seller=self.seller, status=value)
                make_listing_image(listing)
                ends_at = listing.ends_at

                # === Act ===
                response = self.publish(7, self.url_for(listing))

                # === Assert ===
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                self.assertEqual(response.json()['errors'][0]['message'], 'Only a draft can be published.')
                listing.refresh_from_db()
                self.assertEqual(listing.ends_at, ends_at)

    def test_it_cannot_publish_twice(self):
        # === Arrange ===
        self.publish(7)

        # === Act === (a second click must not restart the clock)
        with mock.patch('listings.services.drafts.timezone.now', return_value=NOW + timedelta(days=1)):
            response = self.client.post(self.url, data={'duration_days': 14})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.published_at, NOW)
        self.assertEqual(self.listing.ends_at, NOW + timedelta(days=7))

    def test_it_makes_the_listing_read_only(self):
        # === Arrange ===
        self.publish(7)
        photo = self.listing.images.get()
        detail = reverse('listings:listing-detail', args=[self.listing.pk])
        upload = reverse('listings:listing-image-list', args=[self.listing.pk])
        photo_url = reverse('listings:listing-image-detail', args=[self.listing.pk, photo.pk])

        # === Act ===
        responses = {
            'edit': self.client.patch(detail, data={'title': 'Changed'}),
            'delete': self.client.delete(detail),
            'upload': self.client.post(upload, data={'image': make_image_file()}, format='multipart'),
            'remove photo': self.client.delete(photo_url),
        }

        # === Assert ===
        for action, response in responses.items():
            with self.subTest(action=action):
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.images.count(), 1)

    def test_it_returns_forbidden_for_other_users_published_listing(self):
        # === Arrange ===
        listing = make_active_listing(seller=self.other)

        # === Act ===
        response = self.publish(7, self.url_for(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_it_returns_not_found_for_other_users_draft(self):
        # === Arrange ===
        listing = make_listing(seller=self.other)
        make_listing_image(listing)

        # === Act ===
        response = self.publish(7, self.url_for(listing))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'draft')

    def test_it_returns_not_found_for_unknown_listing(self):
        # === Act ===
        response = self.publish(7, reverse('listings:listing-publish', args=[999999]))

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_it_returns_error_if_not_authenticated(self):
        # === Arrange ===
        self.client.logout()

        # === Act ===
        response = self.publish(7)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'draft')

    def test_it_does_not_allow_get(self):
        # === Act ===
        response = self.client.get(self.url)

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'listing_write': '2/min'})
    def test_it_returns_error_if_requests_too_frequent(self):
        # === Act ===
        for _ in range(3):
            response = self.client.post(self.url, data={'duration_days': 99})

        # === Assert ===
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
