# coding=utf-8
"""Tests for the Auth REST API namespace (login, register, password reset, WebAuthn)."""

from __future__ import annotations

import uuid

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import User


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/login with valid credentials returns a token."""
    suffix = uuid.uuid4().hex[:8]
    username = f'loginok_{suffix}'
    password = 'Str0ngP@ss!'

    with app.app_context():
        user = User(username=username, email=f'{username}@expenseapp.ch', locale='en')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

    resp = client.post('/apis/auth/login', json={
        'username': username,
        'password': password,
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'token' in data
    assert data['username'] == username
    assert 'user_guid' in data


def test_login_missing_fields(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/login with empty body returns 400."""
    resp = client.post('/apis/auth/login', json={})

    assert resp.status_code == 400


def test_login_invalid_credentials(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/login with wrong password returns 401."""
    suffix = uuid.uuid4().hex[:8]
    username = f'badpw_{suffix}'

    with app.app_context():
        user = User(username=username, email=f'{username}@expenseapp.ch', locale='en')
        user.set_password('RealPassword1!')
        db.session.add(user)
        db.session.commit()

    resp = client.post('/apis/auth/login', json={
        'username': username,
        'password': 'WrongPassword',
    })

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_success(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/register with unique credentials returns 201."""
    suffix = uuid.uuid4().hex[:8]
    username = f'newreg_{suffix}'
    email = f'{username}@expenseapp.ch'

    resp = client.post('/apis/auth/register', json={
        'username': username,
        'email': email,
        'locale': 'en',
    })

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['username'] == username
    assert data['email'] == email
    assert 'guid' in data

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user is not None


def test_register_with_password_returns_token(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/register with a password returns a usable API token."""
    suffix = uuid.uuid4().hex[:8]
    username = f'pwreg_{suffix}'
    email = f'{username}@expenseapp.ch'
    password = 'S3cretP@ss!'

    resp = client.post('/apis/auth/register', json={
        'username': username,
        'email': email,
        'locale': 'en',
        'password': password,
    })

    assert resp.status_code == 201
    data = resp.get_json()
    assert 'token' in data
    token = data['token']
    guid = data['guid']

    # The token should authenticate subsequent requests
    me_resp = client.get(
        f'/apis/users/{guid}',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        },
    )
    assert me_resp.status_code == 200
    me_data = me_resp.get_json()
    assert me_data['username'] == username


def test_register_duplicate_username(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/register with an existing username returns 400."""
    suffix = uuid.uuid4().hex[:8]
    username = f'dupu_{suffix}'

    with app.app_context():
        user = User(username=username, email=f'{username}@expenseapp.ch', locale='en')
        user.set_password('AnyPass1!')
        db.session.add(user)
        db.session.commit()

    resp = client.post('/apis/auth/register', json={
        'username': username,
        'email': f'other_{suffix}@expenseapp.ch',
        'locale': 'en',
    })

    assert resp.status_code == 400
    data = resp.get_json()
    assert 'username' in data.get('message', '').lower()


def test_register_duplicate_email(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/register with an existing email returns 400."""
    suffix = uuid.uuid4().hex[:8]
    email = f'dupe_{suffix}@expenseapp.ch'

    with app.app_context():
        user = User(username=f'orig_{suffix}', email=email, locale='en')
        user.set_password('AnyPass1!')
        db.session.add(user)
        db.session.commit()

    resp = client.post('/apis/auth/register', json={
        'username': f'another_{suffix}',
        'email': email,
        'locale': 'en',
    })

    assert resp.status_code == 400
    data = resp.get_json()
    assert 'email' in data.get('message', '').lower()


def test_register_missing_fields(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/register with missing username/email returns 400."""
    resp = client.post('/apis/auth/register', json={
        'locale': 'en',
    })

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def test_reset_password_success(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/reset-password for a known email returns 200."""
    suffix = uuid.uuid4().hex[:8]
    email = f'reset_{suffix}@expenseapp.ch'

    with app.app_context():
        user = User(username=f'reset_{suffix}', email=email, locale='en')
        user.set_password('OldPass1!')
        db.session.add(user)
        db.session.commit()

    resp = client.post('/apis/auth/reset-password', json={
        'email': email,
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'message' in data


def test_reset_password_nonexistent_email(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/reset-password for unknown email still returns 200 (no enumeration)."""
    resp = client.post('/apis/auth/reset-password', json={
        'email': 'nobody@example.com',
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'message' in data


# ---------------------------------------------------------------------------
# Set password
# ---------------------------------------------------------------------------

def test_set_password_missing_fields(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/set-password with empty body returns 400."""
    resp = client.post('/apis/auth/set-password', json={})

    assert resp.status_code == 400


def test_set_password_invalid_token(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/set-password with a bogus token returns 400."""
    resp = client.post('/apis/auth/set-password', json={
        'token': 'totally-invalid-jwt-token',
        'password': 'NewPass123!',
    })

    assert resp.status_code == 400
    data = resp.get_json()
    assert 'invalid' in data.get('message', '').lower() or 'expired' in data.get('message', '').lower()


def test_set_password_success(app: Flask, client: FlaskClient) -> None:
    """POST /apis/auth/set-password with a valid reset token sets the new password."""
    suffix = uuid.uuid4().hex[:8]
    username = f'setpw_{suffix}'
    new_password = 'BrandNewPass1!'

    with app.app_context():
        user = User(username=username, email=f'{username}@expenseapp.ch', locale='en')
        user.set_password('OldPassword1!')
        db.session.add(user)
        db.session.commit()
        token = user.get_reset_password_token()

    resp = client.post('/apis/auth/set-password', json={
        'token': token,
        'password': new_password,
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'message' in data

    # Verify the new password actually works
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        assert user.check_password(new_password) is True


# ---------------------------------------------------------------------------
# WebAuthn
# ---------------------------------------------------------------------------

def test_webauthn_register_options_requires_auth(
    app: Flask,
    client: FlaskClient,
) -> None:
    """POST /apis/auth/webauthn/register/options without a token returns 401."""
    resp = client.post('/apis/auth/webauthn/register/options', json={})

    assert resp.status_code == 401


def test_webauthn_authenticate_options_no_auth_needed(
    app: Flask,
    client: FlaskClient,
) -> None:
    """POST /apis/auth/webauthn/authenticate/options succeeds without auth."""
    resp = client.post('/apis/auth/webauthn/authenticate/options', json={})

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'options' in data
    assert 'session_id' in data


def test_webauthn_authenticate_verify_invalid(
    app: Flask,
    client: FlaskClient,
) -> None:
    """POST /apis/auth/webauthn/authenticate/verify with bad data returns 401."""
    resp = client.post('/apis/auth/webauthn/authenticate/verify', json={
        'session_id': uuid.uuid4().hex,
        'credential': {'id': 'fake', 'type': 'public-key'},
    })

    assert resp.status_code == 401
