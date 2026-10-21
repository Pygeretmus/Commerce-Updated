from decimal import Decimal

MIN_PRICE = Decimal('0.01')

# A seller cannot pile up unlimited drafts
MAX_DRAFTS = 20

# How long an auction can run, in days; the seller picks one when publishing
DURATIONS_DAYS = (1, 3, 5, 7, 14)
