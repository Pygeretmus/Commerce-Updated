from datetime import timedelta
from decimal import Decimal

MIN_PRICE = Decimal('0.01')

# A seller cannot pile up unlimited drafts
MAX_DRAFTS = 20

# How long an auction can run, in days; the seller picks one when publishing
DURATIONS_DAYS = (1, 3, 5, 7, 14)

# A bid in the last minutes pushes the end of the auction so that nobody can win by sniping
SNIPING_WINDOW = timedelta(minutes=2)

# What fits into Decimal(12, 2)
MAX_BID = Decimal('9999999999.99')

CENT = Decimal('0.01')

BID_STATUSES = ('winning', 'outbid', 'won', 'lost')
