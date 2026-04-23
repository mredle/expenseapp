# coding=utf-8
"""Shared error response helpers for the REST API."""

from __future__ import annotations

from flask import jsonify
from flask_restx import abort
from werkzeug.http import HTTP_STATUS_CODES


def error_response(status_code: int, message: str | None = None) -> tuple:
    """Return a JSON error response as a ``(body, status_code)`` tuple.

    Used by Flask error handlers (404, 500) and flask-httpauth error
    callbacks where a *return value* is expected.  API resource methods
    that are decorated with ``@marshal_with`` should use
    :func:`bad_request` instead, which raises via ``flask_restx.abort``.
    """
    payload = {'error': HTTP_STATUS_CODES.get(status_code, 'Unknown error')}
    if message:
        payload['message'] = message
    response = jsonify(payload)
    response.status_code = status_code
    return response


def bad_request(message: str) -> None:
    """Raise a 400 Bad Request via ``flask_restx.abort``.

    This bypasses ``@marshal_with`` so the error status code is preserved.
    Must only be called from API resource methods, never from Flask error
    handlers.
    """
    abort(400, message=message)
