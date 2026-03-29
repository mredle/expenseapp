# -*- coding: utf-8 -*-
"""Shared error response helpers for the REST API."""

from __future__ import annotations

from flask import jsonify
from werkzeug.http import HTTP_STATUS_CODES


def error_response(status_code: int, message: str | None = None) -> tuple:
    """Build a JSON error response with an optional human-readable message."""
    payload: dict[str, str] = {'error': HTTP_STATUS_CODES.get(status_code, 'Unknown error')}
    if message:
        payload['message'] = message
    response = jsonify(payload)
    response.status_code = status_code
    return response


def bad_request(message: str) -> tuple:
    """Convenience wrapper for a 400 Bad Request response."""
    return error_response(400, message)
