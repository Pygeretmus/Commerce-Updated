import os

from django.core.management import call_command
from django.test import TestCase


class OpenAPISchemaTest(TestCase):
    def test_it_generates_a_valid_schema_without_warnings(self):
        # === Act & Assert === (a view that drf-spectacular cannot describe would be missing from Swagger)
        call_command('spectacular', validate=True, fail_on_warn=True, file=os.devnull)
