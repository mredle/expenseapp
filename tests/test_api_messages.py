# coding=utf-8
"""Tests for the Messages REST API namespace (/apis/messages/)."""

from __future__ import annotations

import json
import uuid

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import User
from tests.conftest import _api_headers


def test_list_messages_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/messages/ returns 200 with paginated message list."""
    client, token = api_client
    resp = client.get('/apis/messages/', headers=_api_headers(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data
    assert 'has_next' in data
    assert 'has_prev' in data
    assert data['items'] == []
    assert data['total'] == 0


def test_list_messages_requires_auth(app: Flask, client: FlaskClient) -> None:
    """GET /apis/messages/ without auth returns 401."""
    resp = client.get('/apis/messages/', headers={'Accept': 'application/json'})
    assert resp.status_code == 401


def test_send_message_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/messages/ sends a message to another user and returns 201."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        recipient = User(
            username=f'recipient_{suffix}',
            email=f'recipient_{suffix}@test.ch',
            locale='en',
        )
        recipient.set_password('pass')
        db.session.add(recipient)
        db.session.commit()
        recipient_id = recipient.id

    resp = client.post(
        '/apis/messages/',
        headers=_api_headers(token),
        data=json.dumps({'recipient_id': recipient_id, 'body': 'Hello!'}),
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['body'] == 'Hello!'
    assert data['recipient'] == f'recipient_{suffix}'


def test_send_message_missing_fields(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/messages/ with missing fields returns 400."""
    client, token = api_client
    resp = client.post(
        '/apis/messages/',
        headers=_api_headers(token),
        data=json.dumps({}),
    )
    assert resp.status_code == 400


def test_send_message_requires_auth(app: Flask, client: FlaskClient) -> None:
    """POST /apis/messages/ without auth returns 401."""
    resp = client.post(
        '/apis/messages/',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        data=json.dumps({'recipient_id': 1, 'body': 'test'}),
    )
    assert resp.status_code == 401


def test_notifications_success(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/messages/notifications returns 200 with items list."""
    client, token = api_client
    resp = client.get(
        '/apis/messages/notifications?since=0',
        headers=_api_headers(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data


def test_notifications_requires_auth(app: Flask, client: FlaskClient) -> None:
    """GET /apis/messages/notifications without auth returns 401."""
    resp = client.get(
        '/apis/messages/notifications?since=0',
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 401


def test_send_and_list_messages(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """Send a message then list messages and verify it appears."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        recipient = User(
            username=f'recip_{suffix}',
            email=f'recip_{suffix}@test.ch',
            locale='en',
        )
        recipient.set_password('pass')
        db.session.add(recipient)
        db.session.commit()
        recipient_id = recipient.id

    body_text = f'Integration test message {suffix}'
    send_resp = client.post(
        '/apis/messages/',
        headers=_api_headers(token),
        data=json.dumps({'recipient_id': recipient_id, 'body': body_text}),
    )
    assert send_resp.status_code == 201

    list_resp = client.get('/apis/messages/', headers=_api_headers(token))
    assert list_resp.status_code == 200
    data = list_resp.get_json()
    assert data['total'] >= 1
    bodies = [m['body'] for m in data['items']]
    assert body_text in bodies
