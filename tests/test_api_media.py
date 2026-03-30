# coding=utf-8
"""Tests for the Media REST API namespace (/apis/media/)."""

from __future__ import annotations

import json
import uuid

from flask import Flask
from flask.testing import FlaskClient

from tests.conftest import _api_headers


def test_serve_file_not_found(app: Flask, client: FlaskClient) -> None:
    """GET /apis/media/files/<id> returns 404 for a nonexistent file."""
    resp = client.get('/apis/media/files/99999', headers={'Accept': 'application/json'})
    assert resp.status_code == 404


def test_serve_file_no_auth_needed(app: Flask, client: FlaskClient) -> None:
    """GET /apis/media/files/<id> does not require authentication.

    A missing file returns 404, not 401.
    """
    resp = client.get('/apis/media/files/99999', headers={'Accept': 'application/json'})
    assert resp.status_code != 401
    assert resp.status_code == 404


def test_get_image_requires_auth(app: Flask, client: FlaskClient) -> None:
    """GET /apis/media/images/<guid> without auth returns 401."""
    fake_guid = uuid.uuid4().hex
    resp = client.get(
        f'/apis/media/images/{fake_guid}',
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 401


def test_get_image_not_found(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """GET /apis/media/images/<guid> returns 404 for a nonexistent image."""
    client, token = api_client
    fake_guid = uuid.uuid4().hex
    resp = client.get(
        f'/apis/media/images/{fake_guid}',
        headers=_api_headers(token),
    )
    assert resp.status_code == 404


def test_rotate_image_requires_auth(app: Flask, client: FlaskClient) -> None:
    """POST /apis/media/images/<guid>/rotate without auth returns 401."""
    fake_guid = uuid.uuid4().hex
    resp = client.post(
        f'/apis/media/images/{fake_guid}/rotate',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        data=json.dumps({'degree': 90}),
    )
    assert resp.status_code == 401


def test_rotate_image_not_found(app: Flask, api_client: tuple[FlaskClient, str]) -> None:
    """POST /apis/media/images/<guid>/rotate returns 404 for a nonexistent image."""
    client, token = api_client
    fake_guid = uuid.uuid4().hex
    resp = client.post(
        f'/apis/media/images/{fake_guid}/rotate',
        headers=_api_headers(token),
        data=json.dumps({'degree': 90}),
    )
    assert resp.status_code == 404
