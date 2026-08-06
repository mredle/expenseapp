# coding=utf-8
"""Tests for the Tokens REST API namespace (issue, refresh, revoke)."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import User
from tests.conftest import _api_headers


def _basic_headers(username: str, password: str) -> dict[str, str]:
    """Return HTTP Basic auth headers for the token endpoint."""
    raw = f'{username}:{password}'.encode('utf-8')
    return {
        'Authorization': f'Basic {base64.b64encode(raw).decode("ascii")}',
        'Accept': 'application/json',
    }


def _make_user(app: Flask, password: str = 'pw') -> tuple[str, str]:
    """Create a user and return its (username, token)."""
    suffix = uuid.uuid4().hex[:8]
    username = f'tok_{suffix}'
    with app.app_context():
        user = User(username=username, email=f'{username}@example.com', locale='en')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        token = user.get_token()
        db.session.commit()
        return username, token


# ---------------------------------------------------------------------------
# Token issuing exposes expiry
# ---------------------------------------------------------------------------

def test_post_token_returns_expires_at(app: Flask, client: FlaskClient) -> None:
    """POST /apis/tokens/ returns the token together with its expiry."""
    username, _token = _make_user(app)

    resp = client.post('/apis/tokens/', headers=_basic_headers(username, 'pw'))

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['token']
    assert data['expires_at']
    # Must be parseable and in the future
    expires = datetime.fromisoformat(data['expires_at'])
    assert expires > datetime.now(timezone.utc)


def test_login_returns_expires_at(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/login includes the token expiry."""
    username, _token = _make_user(app)

    resp = client.post('/apis/auth/login', json={'username': username, 'password': 'pw'})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['token']
    assert data['expires_at']
    assert datetime.fromisoformat(data['expires_at']) > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Refresh endpoint
# ---------------------------------------------------------------------------

def test_refresh_requires_authentication(app: Flask, client: FlaskClient) -> None:
    """POST /apis/tokens/refresh without a token returns 401."""
    resp = client.post('/apis/tokens/refresh', headers={'Accept': 'application/json'})
    assert resp.status_code == 401


def test_refresh_rejects_invalid_token(app: Flask, client: FlaskClient) -> None:
    """POST /apis/tokens/refresh with a bogus token returns 401."""
    resp = client.post('/apis/tokens/refresh', headers=_api_headers(uuid.uuid4().hex))
    assert resp.status_code == 401


def test_refresh_rotates_token_and_extends_expiry(app: Flask, client: FlaskClient) -> None:
    """Refreshing issues a new token and pushes the expiry further out.

    Regression guard: ``get_token()`` returns the existing token untouched while
    it is still valid, so the refresh endpoint must force renewal — otherwise it
    would silently no-op and the session would still expire.
    """
    username, original = _make_user(app)

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        original_expiry = user.get_token_expiration()

    resp = client.post('/apis/tokens/refresh', headers=_api_headers(original))

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['token']
    assert data['token'] != original, 'refresh must rotate the token'

    new_expiry = datetime.fromisoformat(data['expires_at'])
    assert new_expiry >= original_expiry


def test_refresh_invalidates_previous_token(app: Flask, client: FlaskClient) -> None:
    """After refreshing, the old token no longer authenticates."""
    username, original = _make_user(app)

    resp = client.post('/apis/tokens/refresh', headers=_api_headers(original))
    assert resp.status_code == 200
    new_token = resp.get_json()['token']

    # The rotated-away token must be rejected
    stale = client.post('/apis/tokens/refresh', headers=_api_headers(original))
    assert stale.status_code == 401

    # The new one still works
    fresh = client.post('/apis/tokens/refresh', headers=_api_headers(new_token))
    assert fresh.status_code == 200


def test_refresh_rejects_expired_token(app: Flask, client: FlaskClient) -> None:
    """An already-expired token cannot be refreshed; the user must log in."""
    username, token = _make_user(app)

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        user.token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()

    resp = client.post('/apis/tokens/refresh', headers=_api_headers(token))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_token force semantics
# ---------------------------------------------------------------------------

def test_get_token_reuses_valid_token_by_default(app: Flask) -> None:
    """Without force, a still-valid token is returned unchanged."""
    username, token = _make_user(app)

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user.get_token() == token


def test_get_token_force_issues_new_token(app: Flask) -> None:
    """With force=True a brand-new token and expiry are issued."""
    username, token = _make_user(app)

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        before = user.get_token_expiration()

        forced = user.get_token(force=True)
        db.session.commit()

        assert forced != token
        assert user.get_token_expiration() >= before
