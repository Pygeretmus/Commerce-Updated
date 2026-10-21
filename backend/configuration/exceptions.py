import logging

from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import set_rollback

logger = logging.getLogger(__name__)


def normalize_errors(detail, field=None):
    """
    Recursively flattens complex nested error structures into a standardized list of error dictionaries.

    It handles a variety of input formats - strings, lists, or nested dictionaries - and extracts
    individual error messages while preserving the context (i.e., which field the error relates to).

    Example:
        Input:
            {
                'name': [ErrorDetail(string='This field is required.', code='required')],
                'avatar': [ErrorDetail(string='No file was submitted.', code='required')],
            }

        Output:
            [
                {"param": "name", "message": "This field is required."},
                {"param": "avatar", "message": "No file was submitted."}
            ]

    Parameters:
    - detail (Any): The error detail object to normalize. This can be a string, list, or dictionary.
    - field (str or None): The name of the field associated with the current error level (used recursively).

    Returns:
    - List[dict]: A flat list of error entries, each containing:
        - 'param': the field name or None
        - 'message': the error message as a string
    """
    errors = []
    if isinstance(detail, list):
        for item in detail:
            if isinstance(item, dict):
                errors.extend(normalize_errors(item, field))
            else:
                errors.append({'param': field, 'message': str(item), 'code': getattr(item, 'code', 'error')})
    elif isinstance(detail, dict):
        for k, v in detail.items():
            errors.extend(normalize_errors(v, field=k))
    else:
        errors.append({'param': field, 'message': str(detail), 'code': getattr(detail, 'code', 'error')})
    return errors


def exception_handler(exc, context):
    """
    Converts common low-level exceptions into standardized API responses,
    ensuring consistent error formatting for clients.

    Behavior:
    - Converts Django's `Http404` exception into `NotFound` (404) APIException.
    - Converts database `IntegrityError` into a generic `APIException` (500).
    - Ensures that authentication's NotAuthenticated has 401 status code.
    - If the resulting exception is an instance of `APIException`, it:
        - Normalizes the error details using `normalize_errors()`.
        - Adds metadata like `status`, `code`, and optional HTTP headers (e.g., `WWW-Authenticate`, `Retry-After`).
        - Returns a `Response` object with a standardized structure:

        Example response:

                   {
                'status': 400,
                'errors': [
                    {'param': 'name', 'message': 'This field is required.', 'code': 'invalid'},
                    {'param': 'avatar', 'message': 'No file was submitted.', 'code': 'invalid'},
                ],
            }


    Parameters:
    - exc (Exception): The original exception raised during request handling.
    - context (dict): Additional context about the request, such as:
        {
            "view": the view instance,
            "request": the originating request object,
            ...
        }

    Returns:
    - Response: A DRF `Response` object with normalized error information.
    - None: If the exception is not recognized or handled here, letting DRF handle it by default.
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound(*exc.args)
    elif isinstance(exc, IntegrityError):
        logger.exception('Database integrity error', exc_info=exc)
        exc = exceptions.APIException()
    elif isinstance(exc, NotAuthenticated):
        exc.status_code = 401

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = f'{exc.wait}'

        errors = normalize_errors(exc.detail)

        data = {'status': exc.status_code, 'errors': errors}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    return None
