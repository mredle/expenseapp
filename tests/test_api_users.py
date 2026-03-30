# coding=utf-8
"""Tests for the Users REST API namespace (/apis/users/)."""

from __future__ import annotations

import json
import uuid

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import User
from tests.conftest import _api_headers


# ---------------------------------------------------------------------------
# GET /apis/users/ — list users
# ---------------------------------------------------------------------------


def test_list_users_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/users/ returns 200 with paginated collection including items key."""
    client, token = api_client
    response = client.get('/apis/users/', headers=_api_headers(token))
    assert response.status_code == 200
    data = response.get_json()
    assert 'items' in data
    assert '_meta' in data
    assert '_links' in data
    assert isinstance(data['items'], list)
    assert data['_meta']['page'] == 1


def test_list_users_requires_auth(app: Flask, client: FlaskClient) -> None:
    """GET /apis/users/ without a bearer token returns 401."""
    response = client.get('/apis/users/', headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    assert response.status_code == 401


def test_list_users_pagination(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/users/ respects page and per_page query parameters."""
    client, token = api_client

    # Create several users to ensure pagination kicks in
    with app.app_context():
        for i in range(5):
            suffix = uuid.uuid4().hex[:8]
            u = User(username=f'pageuser_{i}_{suffix}',
                     email=f'pageuser_{i}_{suffix}@expenseapp.ch',
                     locale='en')
            u.set_password('password')
            db.session.add(u)
        db.session.commit()

    # Request with per_page=2
    response = client.get('/apis/users/?page=1&per_page=2',
                          headers=_api_headers(token))
    assert response.status_code == 200
    data = response.get_json()
    assert len(data['items']) <= 2
    assert data['_meta']['per_page'] == 2
    assert data['_meta']['total_items'] >= 5


# ---------------------------------------------------------------------------
# POST /apis/users/ — create user
# ---------------------------------------------------------------------------


def test_create_user_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/users/ with valid data returns 201 and the created user."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]
    payload = {
        'username': f'newapi_{suffix}',
        'email': f'newapi_{suffix}@expenseapp.ch',
        'password': 'Str0ngP@ss!',
        'locale': 'en',
    }
    response = client.post('/apis/users/',
                           headers=_api_headers(token),
                           data=json.dumps(payload))
    assert response.status_code == 201
    data = response.get_json()
    assert data['username'] == payload['username']

    # Verify user exists in the database
    with app.app_context():
        user = User.query.filter_by(username=payload['username']).first()
        assert user is not None
        assert user.check_password('Str0ngP@ss!')


def test_create_user_missing_fields(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/users/ without required fields returns 400."""
    client, token = api_client

    # Missing password and email
    payload = {'username': f'incomplete_{uuid.uuid4().hex[:8]}'}
    response = client.post('/apis/users/',
                           headers=_api_headers(token),
                           data=json.dumps(payload))
    assert response.status_code == 400


def test_create_user_duplicate_username(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/users/ with an already-taken username returns 400."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]
    username = f'dupuser_{suffix}'

    # Create the first user
    with app.app_context():
        u = User(username=username, email=f'{username}@expenseapp.ch', locale='en')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()

    # Attempt to create a second user with the same username
    payload = {
        'username': username,
        'email': f'other_{suffix}@expenseapp.ch',
        'password': 'password',
        'locale': 'en',
    }
    response = client.post('/apis/users/',
                           headers=_api_headers(token),
                           data=json.dumps(payload))
    assert response.status_code == 400


def test_create_user_duplicate_email(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/users/ with an already-taken email returns 400."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]
    email = f'dupemail_{suffix}@expenseapp.ch'

    # Create the first user
    with app.app_context():
        u = User(username=f'first_{suffix}', email=email, locale='en')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()

    # Attempt to create a second user with the same email
    payload = {
        'username': f'second_{suffix}',
        'email': email,
        'password': 'password',
        'locale': 'en',
    }
    response = client.post('/apis/users/',
                           headers=_api_headers(token),
                           data=json.dumps(payload))
    assert response.status_code == 400


def test_create_user_requires_auth(app: Flask, client: FlaskClient) -> None:
    """POST /apis/users/ without a bearer token returns 401."""
    payload = {
        'username': f'noauth_{uuid.uuid4().hex[:8]}',
        'email': f'noauth_{uuid.uuid4().hex[:8]}@expenseapp.ch',
        'password': 'password',
        'locale': 'en',
    }
    response = client.post('/apis/users/',
                           headers={'Content-Type': 'application/json',
                                    'Accept': 'application/json'},
                           data=json.dumps(payload))
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /apis/users/<guid> — single user
# ---------------------------------------------------------------------------


def test_get_user_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/users/<guid> returns 200 with the correct user data."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        u = User(username=f'getuser_{suffix}',
                 email=f'getuser_{suffix}@expenseapp.ch',
                 locale='en')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        user_guid = str(u.guid)

    response = client.get(f'/apis/users/{user_guid}',
                          headers=_api_headers(token))
    assert response.status_code == 200
    data = response.get_json()
    assert data['username'] == f'getuser_{suffix}'
    assert '_links' in data


def test_get_user_not_found(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/users/<guid> with a nonexistent GUID returns 404."""
    client, token = api_client
    fake_guid = uuid.uuid4().hex
    response = client.get(f'/apis/users/{fake_guid}',
                          headers=_api_headers(token))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /apis/users/<guid> — update user
# ---------------------------------------------------------------------------


def test_update_user_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """PUT /apis/users/<guid> updates the user and returns the new data."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        u = User(username=f'upduser_{suffix}',
                 email=f'upduser_{suffix}@expenseapp.ch',
                 locale='en')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        user_guid = str(u.guid)

    payload = {'about_me': f'Updated bio {suffix}'}
    response = client.put(f'/apis/users/{user_guid}',
                          headers=_api_headers(token),
                          data=json.dumps(payload))
    assert response.status_code == 200
    data = response.get_json()
    assert data['about_me'] == f'Updated bio {suffix}'

    # Verify the change persisted in the database
    with app.app_context():
        u = User.query.filter_by(guid=user_guid).first()
        assert u.about_me == f'Updated bio {suffix}'


def test_update_user_duplicate_username(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """PUT /apis/users/<guid> rejects a username that is already taken."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        # User A — the one we will try to update
        user_a = User(username=f'usera_{suffix}',
                      email=f'usera_{suffix}@expenseapp.ch',
                      locale='en')
        user_a.set_password('password')
        db.session.add(user_a)

        # User B — owns the username we want to steal
        user_b = User(username=f'userb_{suffix}',
                      email=f'userb_{suffix}@expenseapp.ch',
                      locale='en')
        user_b.set_password('password')
        db.session.add(user_b)

        db.session.commit()
        user_a_guid = str(user_a.guid)

    payload = {'username': f'userb_{suffix}'}
    response = client.put(f'/apis/users/{user_a_guid}',
                          headers=_api_headers(token),
                          data=json.dumps(payload))
    assert response.status_code == 400
