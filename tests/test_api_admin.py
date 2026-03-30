# coding=utf-8
"""Tests for the Admin REST API namespace (/apis/admin)."""

from __future__ import annotations

import json
import uuid

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.db_logging import log_add
from app.models import Log, User
from tests.conftest import _api_headers


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


def test_list_logs_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin user can list log entries and receives a paginated response."""
    client, token = api_admin_client

    # Seed a log entry so the response is non-empty.
    with app.app_context():
        admin_user = User.query.filter_by(username='apiadmin').first()
        suffix = uuid.uuid4().hex[:8]
        log_add('INFORMATION', 'test', 'test_msg', f'admin log entry {suffix}', admin_user)

    resp = client.get('/apis/admin/logs?page=1&per_page=25', headers=_api_headers(token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data
    assert 'has_next' in data
    assert 'has_prev' in data
    assert isinstance(data['items'], list)
    assert data['total'] >= 1


def test_list_logs_regular_user(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Regular (non-admin) user can list logs and receives a 200 response."""
    client, token = api_client

    # Seed a log entry for the regular user.
    with app.app_context():
        user = User.query.filter_by(username='apiuser').first()
        suffix = uuid.uuid4().hex[:8]
        log_add('INFORMATION', 'test', 'test_msg', f'user log entry {suffix}', user)

    resp = client.get('/apis/admin/logs?page=1&per_page=25', headers=_api_headers(token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert 'items' in data
    assert isinstance(data['items'], list)


def test_list_logs_requires_auth(client: FlaskClient) -> None:
    """Unauthenticated request to list logs returns 401."""
    resp = client.get(
        '/apis/admin/logs',
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Log detail
# ---------------------------------------------------------------------------


def test_get_log_detail_not_found(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Requesting a non-existent log ID returns 404."""
    client, token = api_admin_client
    resp = client.get('/apis/admin/logs/99999', headers=_api_headers(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def test_list_tasks_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin user can list tasks and receives a paginated response."""
    client, token = api_admin_client
    resp = client.get('/apis/admin/tasks?page=1&per_page=25', headers=_api_headers(token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data
    assert 'has_next' in data
    assert 'has_prev' in data
    assert isinstance(data['items'], list)


def test_list_tasks_requires_auth(client: FlaskClient) -> None:
    """Unauthenticated request to list tasks returns 401."""
    resp = client.get(
        '/apis/admin/tasks',
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 401


def test_launch_task_missing_key(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Launching a task without a key returns 400."""
    client, token = api_admin_client
    resp = client.post(
        '/apis/admin/tasks',
        headers=_api_headers(token),
        data=json.dumps({'amount': 5}),
    )
    assert resp.status_code == 400


def test_launch_task_requires_auth(client: FlaskClient) -> None:
    """Unauthenticated request to launch a task returns 401."""
    resp = client.post(
        '/apis/admin/tasks',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        data=json.dumps({'key': 'WASTE_TIME', 'amount': 1}),
    )
    assert resp.status_code == 401


def test_remove_task_non_admin(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Regular (non-admin) user cannot delete a task and receives 403."""
    client, token = api_client
    fake_guid = uuid.uuid4().hex
    resp = client.delete(
        f'/apis/admin/tasks/{fake_guid}',
        headers=_api_headers(token),
    )
    assert resp.status_code == 403


def test_remove_task_requires_auth(client: FlaskClient) -> None:
    """Unauthenticated request to remove a task returns 401."""
    fake_guid = uuid.uuid4().hex
    resp = client.delete(
        f'/apis/admin/tasks/{fake_guid}',
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_statistics_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin user can retrieve statistics and response contains items list."""
    client, token = api_admin_client
    resp = client.get('/apis/admin/statistics', headers=_api_headers(token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert 'items' in data
    assert isinstance(data['items'], list)
    # Each item should have 'label' and 'count'.
    for item in data['items']:
        assert 'label' in item
        assert 'count' in item


def test_statistics_requires_auth(client: FlaskClient) -> None:
    """Unauthenticated request to statistics endpoint returns 401."""
    resp = client.get(
        '/apis/admin/statistics',
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 401
