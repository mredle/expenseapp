# -*- coding: utf-8 -*-
"""Application-wide error handlers with JSON/HTML content negotiation."""

from __future__ import annotations

from flask import render_template, request

from app import db
from app.errors import bp
from app.apis.errors import error_response as api_error_response
from app.db_logging import log_error


def wants_json_response() -> bool:
    """Return ``True`` if the client prefers JSON over HTML."""
    return request.accept_mimetypes['application/json'] >= \
        request.accept_mimetypes['text/html']


@bp.app_errorhandler(404)
def not_found_error(error: Exception) -> tuple:
    """Handle 404 Not Found errors."""
    if wants_json_response():
        return api_error_response(404)
    log_error(request, '404')
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error: Exception) -> tuple:
    """Handle 500 Internal Server errors with a database rollback."""
    db.session.rollback()
    if wants_json_response():
        return api_error_response(500)
    log_error(request, '500')
    return render_template('errors/500.html'), 500
