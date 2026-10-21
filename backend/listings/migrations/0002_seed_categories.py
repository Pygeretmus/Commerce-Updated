from django.db import migrations

CATEGORIES = [
    ('Antiques', 'antiques'),
    ('Art', 'art'),
    ('Books', 'books'),
    ('Clothing', 'clothing'),
    ('Collectibles', 'collectibles'),
    ('Electronics', 'electronics'),
    ('Home & Garden', 'home-garden'),
    ('Jewelry', 'jewelry'),
    ('Sports', 'sports'),
    ('Toys', 'toys'),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('listings', 'Category')
    for name, slug in CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={'name': name})


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('listings', 'Category')
    Category.objects.filter(slug__in=[slug for _, slug in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('listings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
