from django.db import IntegrityError
from django.http import Http404
from django.test import SimpleTestCase
from rest_framework import exceptions
from rest_framework.exceptions import ErrorDetail

from ..exceptions import exception_handler, normalize_errors


class NormalizeErrorsTest(SimpleTestCase):
    def test_it_handles_a_plain_string(self):
        self.assertEqual(
            normalize_errors('Boom'),
            [{'param': None, 'message': 'Boom', 'code': 'error'}],
        )

    def test_it_keeps_the_code_of_an_error_detail(self):
        self.assertEqual(
            normalize_errors(ErrorDetail('This field is required.', code='required')),
            [{'param': None, 'message': 'This field is required.', 'code': 'required'}],
        )

    def test_it_flattens_a_list_and_applies_the_given_field(self):
        detail = [ErrorDetail('Too short.', code='min_length'), ErrorDetail('Too common.', code='password_too_common')]

        result = normalize_errors(detail, field='password')

        self.assertEqual(
            result,
            [
                {'param': 'password', 'message': 'Too short.', 'code': 'min_length'},
                {'param': 'password', 'message': 'Too common.', 'code': 'password_too_common'},
            ],
        )

    def test_it_flattens_a_dict_into_one_entry_per_message(self):
        detail = {
            'name': [ErrorDetail('This field is required.', code='required')],
            'avatar': [ErrorDetail('No file was submitted.', code='required')],
        }

        result = normalize_errors(detail)

        self.assertEqual(
            result,
            [
                {'param': 'name', 'message': 'This field is required.', 'code': 'required'},
                {'param': 'avatar', 'message': 'No file was submitted.', 'code': 'required'},
            ],
        )

    def test_it_uses_the_innermost_key_for_nested_dicts(self):
        detail = {'user': {'email': [ErrorDetail('Enter a valid email address.', code='invalid')]}}

        result = normalize_errors(detail)

        self.assertEqual(
            result,
            [{'param': 'email', 'message': 'Enter a valid email address.', 'code': 'invalid'}],
        )

    def test_it_handles_dicts_inside_a_list(self):
        # This is what a serializer with many=True produces: one (possibly empty) dict per item
        detail = [{}, {'name': [ErrorDetail('This field is required.', code='required')]}]

        result = normalize_errors(detail)

        self.assertEqual(
            result,
            [{'param': 'name', 'message': 'This field is required.', 'code': 'required'}],
        )

    def test_it_returns_an_empty_list_for_empty_input(self):
        self.assertEqual(normalize_errors([]), [])
        self.assertEqual(normalize_errors({}), [])


class ExceptionHandlerTest(SimpleTestCase):
    def test_it_converts_http404_to_a_404_response(self):
        response = exception_handler(Http404(), {})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {'status': 404, 'errors': [{'param': None, 'message': 'Not found.', 'code': 'not_found'}]},
        )

    def test_it_converts_validation_errors_to_a_400_response(self):
        exc = exceptions.ValidationError({'name': ['This field is required.']})

        response = exception_handler(exc, {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                'status': 400,
                'errors': [{'param': 'name', 'message': 'This field is required.', 'code': 'invalid'}],
            },
        )

    def test_it_converts_not_authenticated_to_a_401_response(self):
        response = exception_handler(exceptions.NotAuthenticated(), {})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['errors'][0]['code'], 'not_authenticated')

    def test_it_does_not_leak_integrity_error_details(self):
        # Requires the fix where the handler logs the IntegrityError and returns a generic APIException
        exc = IntegrityError('duplicate key value violates unique constraint "uniq_secret_constraint"')

        with self.assertLogs('configuration.exceptions', level='ERROR'):
            response = exception_handler(exc, {})

        self.assertEqual(response.status_code, 500)
        self.assertNotIn('uniq_secret_constraint', str(response.data))
        self.assertEqual(response.data['errors'][0]['message'], 'A server error occurred.')

    def test_it_adds_the_www_authenticate_header_when_the_exception_has_one(self):
        exc = exceptions.AuthenticationFailed()
        exc.auth_header = 'Bearer realm="api"'

        response = exception_handler(exc, {})

        self.assertEqual(response['WWW-Authenticate'], 'Bearer realm="api"')

    def test_it_adds_the_retry_after_header_for_throttled_requests(self):
        response = exception_handler(exceptions.Throttled(wait=30), {})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '30')

    def test_it_returns_none_for_exceptions_it_does_not_know(self):
        self.assertIsNone(exception_handler(ValueError('unexpected'), {}))
