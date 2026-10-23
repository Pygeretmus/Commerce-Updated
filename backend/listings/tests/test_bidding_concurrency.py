import itertools
import threading
import time
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from django_dynamic_fixture import G

from ..models import Bid, Listing
from ..services.bidding import BidRejected, place_bid
from .helpers import make_active_listing

User = get_user_model()


def naive_place_bid(listing_id, bidder, amount):
    """The same thing WITHOUT the row lock: read, think, write. Only used to prove the race is real."""
    listing = Listing.objects.get(pk=listing_id)
    count = listing.bids_count
    time.sleep(0.05)  # widen the window between the read and the write
    Bid.objects.create(listing=listing, bidder=bidder, amount=amount)
    Listing.objects.filter(pk=listing_id).update(bids_count=count + 1, current_price=amount)


@skipUnlessDBFeature('has_select_for_update')
class BiddingConcurrencyTest(TransactionTestCase):
    # TransactionTestCase flushes the tables, and the categories are seeded by a migration.
    serialized_rollback = True

    def setUp(self):
        self.seller = G(User)
        self.listing = make_active_listing(
            seller=self.seller, starting_price=Decimal(10), ends_at=timezone.now() + timedelta(days=1)
        )

    def run_parallel(self, jobs):
        """Run callables in threads released at the same moment; return a list of ('ok'|'rejected', code)."""
        barrier = threading.Barrier(len(jobs))
        results = [None] * len(jobs)

        def worker(index, job):
            try:
                barrier.wait()
                job()
                results[index] = ('ok', None)
            except BidRejected as error:
                results[index] = ('rejected', error.get_codes())
            except Exception as error:  # noqa: BLE001 - surface anything unexpected in the assertion
                results[index] = ('error', repr(error))
            finally:
                connection.close()  # every thread owns a connection

        threads = [threading.Thread(target=worker, args=(i, job)) for i, job in enumerate(jobs)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        return results

    def assert_consistent(self):
        listing = Listing.objects.get(pk=self.listing.pk)
        amounts = list(Bid.objects.filter(listing=listing).values_list('amount', flat=True))
        self.assertEqual(listing.bids_count, len(amounts))
        if amounts:
            self.assertEqual(listing.current_price, max(amounts))
            self.assertEqual(listing.top_bid.amount, max(amounts))
        return listing

    def test_it_accepts_exactly_one_of_many_equal_bids(self):
        # === Arrange ===
        bidders = [G(User) for _ in range(10)]
        jobs = [lambda b=b: place_bid(self.listing.pk, b, Decimal(10)) for b in bidders]

        # === Act ===
        results = self.run_parallel(jobs)

        # === Assert ===
        self.assertEqual([r for r in results if r[0] == 'error'], [])
        self.assertEqual(sum(r[0] == 'ok' for r in results), 1)
        self.assertEqual(Bid.objects.count(), 1)
        self.assert_consistent()

    def test_it_keeps_the_listing_consistent_under_rising_bids(self):
        # === Arrange === (each amount is at least a valid next bid for its predecessor)
        amounts = [Decimal(10) + Decimal('0.50') * i for i in range(8)]
        jobs = [lambda a=a: place_bid(self.listing.pk, G(User), a) for a in amounts]

        # === Act ===
        results = self.run_parallel(jobs)

        # === Assert ===
        self.assertEqual([r for r in results if r[0] == 'error'], [])
        listing = self.assert_consistent()
        accepted = sorted(Bid.objects.filter(listing=listing).values_list('amount', flat=True))
        # whatever order the threads ran in, each accepted bid beat the previous one by the increment
        self.assertGreaterEqual(accepted[0], Decimal(10))
        for previous, current in itertools.pairwise(accepted):
            self.assertGreaterEqual(current - previous, Decimal('0.50'))

    def test_it_accepts_one_bid_when_the_same_bidder_double_clicks(self):
        # === Arrange ===
        bidder = G(User)
        jobs = [lambda: place_bid(self.listing.pk, bidder, Decimal(10)) for _ in range(2)]

        # === Act ===
        results = self.run_parallel(jobs)

        # === Assert ===
        self.assertEqual(sorted(r[0] for r in results), ['ok', 'rejected'])
        self.assertEqual(Bid.objects.count(), 1)
        self.assert_consistent()

    def test_it_loses_updates_without_the_lock(self):
        # === Arrange === (proves the tests above are able to catch a race at all)
        bidders = [G(User) for _ in range(5)]
        jobs = []
        for index, bidder in enumerate(bidders):
            amount = Decimal(10) + index
            jobs.append(lambda b=bidder, a=amount: naive_place_bid(self.listing.pk, b, a))

        # === Act ===
        self.run_parallel(jobs)

        # === Assert === (five bids were stored, but the counter missed some of them)
        self.assertEqual(Bid.objects.count(), 5)
        self.assertLess(Listing.objects.get(pk=self.listing.pk).bids_count, 5)
