# coding=utf-8
"""Tests for the new upload and admin-toggle API endpoints.

Covers:
  POST /apis/users/<guid>/picture
  PUT  /apis/users/<guid>/admin
  POST /apis/events/<guid>/picture
  POST /apis/events/<guid>/users/<user_guid>/picture
  POST /apis/events/<guid>/expenses/<expense_guid>/receipt
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timezone

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import Currency, Event, EventUser, Expense, User
from tests.conftest import _api_headers, _get_api_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _png_upload() -> tuple[bytes, str]:
    """Return (file bytes, filename) for a minimal valid PNG."""
    return _PNG_1PX, 'test.png'


# ---------------------------------------------------------------------------
# POST /apis/users/<guid>/picture
# ---------------------------------------------------------------------------


def test_upload_user_picture_self(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """A user can upload their own profile picture and receives image metadata."""
    client, token = api_client
    with app.app_context():
        user = User.query.filter_by(username='apiuser').first()
        user_guid = str(user.guid)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/users/{user_guid}/picture',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    body = response.get_json()
    assert 'guid' in body
    assert 'url' in body
    assert 'width' in body
    assert 'height' in body


def test_upload_user_picture_other_user_forbidden(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """A non-admin user cannot upload a picture for another user."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        other = User(username=f'other_{suffix}',
                     email=f'other_{suffix}@expenseapp.ch',
                     locale='en')
        other.set_password('password')
        db.session.add(other)
        db.session.commit()
        other_guid = str(other.guid)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/users/{other_guid}/picture',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 403


def test_upload_user_picture_admin_can_upload_for_others(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """An admin user can upload a profile picture for any user."""
    client, token = api_admin_client
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        target = User(username=f'target_{suffix}',
                      email=f'target_{suffix}@expenseapp.ch',
                      locale='en')
        target.set_password('password')
        db.session.add(target)
        db.session.commit()
        target_guid = str(target.guid)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/users/{target_guid}/picture',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201


def test_upload_user_picture_no_file(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """POST /apis/users/<guid>/picture without a file returns 400."""
    client, token = api_client
    with app.app_context():
        user = User.query.filter_by(username='apiuser').first()
        user_guid = str(user.guid)

    response = client.post(
        f'/apis/users/{user_guid}/picture',
        headers=_api_headers(token),
        data=json.dumps({}),
    )
    assert response.status_code == 400


def test_upload_user_picture_requires_auth(
    app: Flask,
    client: FlaskClient,
    api_client: tuple[FlaskClient, str],
) -> None:
    """POST /apis/users/<guid>/picture without a token returns 401."""
    _client, _token = api_client
    with app.app_context():
        user = User.query.filter_by(username='apiuser').first()
        user_guid = str(user.guid)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/users/{user_guid}/picture',
        headers={'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /apis/users/<guid>/admin
# ---------------------------------------------------------------------------


def test_grant_admin_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """An admin can grant admin privileges to another user."""
    client, token = api_admin_client
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        target = User(username=f'grant_{suffix}',
                      email=f'grant_{suffix}@expenseapp.ch',
                      locale='en')
        target.set_password('password')
        db.session.add(target)
        db.session.commit()
        target_guid = str(target.guid)

    response = client.put(
        f'/apis/users/{target_guid}/admin',
        headers=_api_headers(token),
        data=json.dumps({'is_admin': True}),
    )
    assert response.status_code == 200
    with app.app_context():
        u = User.query.filter_by(guid=target_guid).first()
        assert u.is_admin is True


def test_revoke_admin_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """An admin can revoke admin privileges from another user."""
    client, token = api_admin_client
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        target = User(username=f'revoke_{suffix}',
                      email=f'revoke_{suffix}@expenseapp.ch',
                      locale='en')
        target.set_password('password')
        target.is_admin = True
        db.session.add(target)
        db.session.commit()
        target_guid = str(target.guid)

    response = client.put(
        f'/apis/users/{target_guid}/admin',
        headers=_api_headers(token),
        data=json.dumps({'is_admin': False}),
    )
    assert response.status_code == 200
    with app.app_context():
        u = User.query.filter_by(guid=target_guid).first()
        assert u.is_admin is False


def test_set_admin_non_admin_forbidden(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """A non-admin user cannot modify admin privileges."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        target = User(username=f'target2_{suffix}',
                      email=f'target2_{suffix}@expenseapp.ch',
                      locale='en')
        target.set_password('password')
        db.session.add(target)
        db.session.commit()
        target_guid = str(target.guid)

    response = client.put(
        f'/apis/users/{target_guid}/admin',
        headers=_api_headers(token),
        data=json.dumps({'is_admin': True}),
    )
    assert response.status_code == 403


def test_set_admin_missing_field(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """PUT /apis/users/<guid>/admin without is_admin field returns 400."""
    client, token = api_admin_client
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        target = User(username=f'missing_{suffix}',
                      email=f'missing_{suffix}@expenseapp.ch',
                      locale='en')
        target.set_password('password')
        db.session.add(target)
        db.session.commit()
        target_guid = str(target.guid)

    response = client.put(
        f'/apis/users/{target_guid}/admin',
        headers=_api_headers(token),
        data=json.dumps({}),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /apis/events/<guid>/picture
# ---------------------------------------------------------------------------


def test_upload_event_picture_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """The event admin can upload a cover picture for their event."""
    client, token = api_client
    with app.app_context():
        event_guid = str(api_event.guid)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/events/{event_guid}/picture',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    body = response.get_json()
    assert 'guid' in body
    assert 'url' in body


def test_upload_event_picture_non_admin_forbidden(
    app: Flask,
    api_event: Event,
) -> None:
    """A non-admin user cannot upload an event cover picture."""
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        other = User(username=f'notadmin_{suffix}',
                     email=f'notadmin_{suffix}@expenseapp.ch',
                     locale='en')
        other.set_password('password')
        db.session.add(other)
        db.session.commit()
        event_guid = str(api_event.guid)
        other_guid = str(other.guid)

    # Get token for the non-admin user
    tmp_app = app
    with tmp_app.test_client() as c:
        token = _get_api_token(tmp_app, c, f'notadmin_{suffix}', 'password')
        data, filename = _png_upload()
        response = c.post(
            f'/apis/events/{event_guid}/picture',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            data={'image': (io.BytesIO(data), filename)},
            content_type='multipart/form-data',
        )
    assert response.status_code == 403


def test_upload_event_picture_no_file(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """POST /apis/events/<guid>/picture without a file returns 400."""
    client, token = api_client
    with app.app_context():
        event_guid = str(api_event.guid)

    response = client.post(
        f'/apis/events/{event_guid}/picture',
        headers=_api_headers(token),
        data=json.dumps({}),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /apis/events/<guid>/users/<user_guid>/picture
# ---------------------------------------------------------------------------


def test_upload_event_user_picture_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """An authenticated user can upload a picture for an event user."""
    client, token = api_client
    with app.app_context():
        event_guid = str(api_event.guid)
        # Get the admin EventUser GUID (created by api_event fixture)
        eu = EventUser.query.filter_by(event_id=api_event.id).first()
        eu_guid = str(eu.guid)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/events/{event_guid}/users/{eu_guid}/picture',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    body = response.get_json()
    assert 'guid' in body
    assert 'url' in body


def test_upload_event_user_picture_no_file(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """POST /apis/events/<guid>/users/<user_guid>/picture without a file returns 400."""
    client, token = api_client
    with app.app_context():
        event_guid = str(api_event.guid)
        eu = EventUser.query.filter_by(event_id=api_event.id).first()
        eu_guid = str(eu.guid)

    response = client.post(
        f'/apis/events/{event_guid}/users/{eu_guid}/picture',
        headers=_api_headers(token),
        data=json.dumps({}),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /apis/events/<guid>/expenses/<expense_guid>/receipt
# ---------------------------------------------------------------------------


def _create_expense(app: Flask, api_event: Event) -> str:
    """Create a minimal expense and return its GUID."""
    with app.app_context():
        event = db.session.get(Event, api_event.id)
        eu = EventUser.query.filter_by(event_id=event.id).first()
        expense = Expense(
            user=eu,
            event=event,
            currency=event.base_currency,
            amount=10.0,
            affected_users=[eu],
            date=datetime.now(timezone.utc),
        )
        db.session.add(expense)
        db.session.commit()
        return str(expense.guid)


def test_upload_expense_receipt_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """An authenticated user can upload a receipt for an expense."""
    client, token = api_client
    with app.app_context():
        event_guid = str(api_event.guid)
    expense_guid = _create_expense(app, api_event)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/events/{event_guid}/expenses/{expense_guid}/receipt',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 201
    body = response.get_json()
    assert 'guid' in body
    assert 'url' in body


def test_upload_expense_receipt_no_file(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """POST /apis/events/<guid>/expenses/<expense_guid>/receipt without a file returns 400."""
    client, token = api_client
    with app.app_context():
        event_guid = str(api_event.guid)
    expense_guid = _create_expense(app, api_event)

    response = client.post(
        f'/apis/events/{event_guid}/expenses/{expense_guid}/receipt',
        headers=_api_headers(token),
        data=json.dumps({}),
    )
    assert response.status_code == 400


def test_upload_expense_receipt_requires_auth(
    app: Flask,
    client: FlaskClient,
    api_event: Event,
) -> None:
    """POST receipt without a token returns 401."""
    with app.app_context():
        event_guid = str(api_event.guid)
    expense_guid = _create_expense(app, api_event)

    data, filename = _png_upload()
    response = client.post(
        f'/apis/events/{event_guid}/expenses/{expense_guid}/receipt',
        headers={'Accept': 'application/json'},
        data={'image': (io.BytesIO(data), filename)},
        content_type='multipart/form-data',
    )
    assert response.status_code == 401
