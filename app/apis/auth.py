# -*- coding: utf-8 -*-
"""HTTP authentication handlers for the REST API (Basic + Token)."""

from __future__ import annotations

from flask import g
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth

from app.models import User
from app.apis.errors import error_response

basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth()


@basic_auth.verify_password
def verify_password(username: str, password: str) -> bool:
    """Verify username/password credentials and store the user in ``g``."""
    user = User.query.filter_by(username=username).first()
    if user is None:
        return False
    g.current_user = user
    return user.check_password(password)


@basic_auth.error_handler
def basic_auth_error() -> tuple:
    """Return a 401 error response for failed basic auth."""
    return error_response(401)


@token_auth.verify_token
def verify_token(token: str) -> bool:
    """Verify an API token and store the user in ``g``."""
    g.current_user = User.check_token(token) if token else None
    return g.current_user is not None


@token_auth.error_handler
def token_auth_error() -> tuple:
    """Return a 401 error response for failed token auth."""
    return error_response(401)
