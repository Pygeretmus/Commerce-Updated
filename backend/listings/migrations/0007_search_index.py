from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations


def search_index() -> GinIndex:
    # Must be the same expression as listings.filters.SEARCH_VECTOR, or PostgreSQL will not use the index
    return GinIndex(SearchVector('title', 'description', config='english'), name='listing_search_gin')


def add_index(apps, schema_editor):
    # Full-text search is a PostgreSQL feature; other databases fall back to LIKE and need no index
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.add_index(apps.get_model('listings', 'Listing'), search_index())


def remove_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.remove_index(apps.get_model('listings', 'Listing'), search_index())


class Migration(migrations.Migration):
    dependencies = [('listings', '0006_watch')]

    operations = [migrations.RunPython(add_index, remove_index)]
