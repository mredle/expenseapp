# coding=utf-8
"""Tests for the Backups REST API namespace (/apis/backups/)."""

from __future__ import annotations

import io
import json
import uuid

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import BackupSet, Currency, User
from app.services import backup_service
from tests.conftest import _api_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_currency(app: Flask) -> None:
    """Create a CHF currency if not already present."""
    with app.app_context():
        if not Currency.query.filter_by(code='CHF').first():
            c = Currency(code='CHF', name='Swiss Franc', number=756, exponent=2,
                         inCHF=1.0, description='Test')
            db.session.add(c)
            db.session.commit()


# ---------------------------------------------------------------------------
# GET /apis/backups (list)
# ---------------------------------------------------------------------------

def test_list_backups_admin(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can list backup sets and gets a paginated response."""
    client, token = api_admin_client
    resp = client.get('/apis/backups', headers=_api_headers(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data


def test_list_backups_non_admin(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Non-admin receives 403 when listing backup sets."""
    client, token = api_client
    resp = client.get('/apis/backups', headers=_api_headers(token))
    assert resp.status_code == 403


def test_list_backups_unauthenticated(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Unauthenticated request returns 401."""
    resp = client.get('/apis/backups', headers={'Accept': 'application/json'})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /apis/backups (create)
# ---------------------------------------------------------------------------

def test_create_backup_admin(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can create a backup set via the API."""
    client, token = api_admin_client
    suffix = uuid.uuid4().hex[:6]
    payload = {
        'name': f'API backup {suffix}',
        'segment_types': ['logs', 'system'],
    }
    resp = client.post('/apis/backups', headers=_api_headers(token), data=json.dumps(payload))
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'guid' in data
    assert 'message' in data


def test_create_backup_missing_name(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Creating a backup without a name returns 400."""
    client, token = api_admin_client
    resp = client.post('/apis/backups', headers=_api_headers(token),
                       data=json.dumps({'segment_types': ['logs']}))
    assert resp.status_code == 400


def test_create_backup_non_admin(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Non-admin receives 403 when creating a backup."""
    client, token = api_client
    payload = {'name': 'Non-admin backup', 'segment_types': ['logs']}
    resp = client.post('/apis/backups', headers=_api_headers(token), data=json.dumps(payload))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /apis/backups/<guid>
# ---------------------------------------------------------------------------

def test_get_backup_admin(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can retrieve a backup set by GUID."""
    client, token = api_admin_client
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        cr = backup_service.create_backup(name='Get test', segment_types=['logs'], user=admin)
        guid = str(cr.backup_set.guid)

    resp = client.get(f'/apis/backups/{guid}', headers=_api_headers(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == guid
    assert 'segments' in data


def test_get_backup_not_found(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Requesting a non-existent backup GUID returns 404."""
    client, token = api_admin_client
    fake_guid = uuid.uuid4().hex
    resp = client.get(f'/apis/backups/{fake_guid}', headers=_api_headers(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /apis/backups/<guid>
# ---------------------------------------------------------------------------

def test_delete_backup_admin(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can delete a backup set via the API."""
    client, token = api_admin_client
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        cr = backup_service.create_backup(name='Del test', segment_types=['logs'], user=admin)
        guid = str(cr.backup_set.guid)

    resp = client.delete(f'/apis/backups/{guid}', headers=_api_headers(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == guid


def test_delete_backup_non_admin(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Non-admin receives 403 when deleting a backup."""
    client, token = api_client
    resp = client.delete(f'/apis/backups/{uuid.uuid4().hex}', headers=_api_headers(token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /apis/backups/<guid>/restore
# ---------------------------------------------------------------------------

def test_restore_backup_invalid_strategy(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Restoring with an unknown strategy returns 400."""
    client, token = api_admin_client
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        cr = backup_service.create_backup(name='Restore invalid', segment_types=['logs'], user=admin)
        guid = str(cr.backup_set.guid)

    resp = client.post(
        f'/apis/backups/{guid}/restore',
        headers=_api_headers(token),
        data=json.dumps({'strategy': 'invalid_strategy'}),
    )
    assert resp.status_code == 400


def test_restore_backup_not_found(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Restoring a non-existent backup GUID returns 404."""
    client, token = api_admin_client
    resp = client.post(
        f'/apis/backups/{uuid.uuid4().hex}/restore',
        headers=_api_headers(token),
        data=json.dumps({'strategy': 'skip'}),
    )
    assert resp.status_code == 404


def test_restore_backup_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can launch a restore task for an existing backup set."""
    client, token = api_admin_client
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        cr = backup_service.create_backup(name='Restore ok', segment_types=['logs'], user=admin)
        guid = str(cr.backup_set.guid)

    resp = client.post(
        f'/apis/backups/{guid}/restore',
        headers=_api_headers(token),
        data=json.dumps({'strategy': 'skip'}),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'message' in data


# ---------------------------------------------------------------------------
# GET /apis/backups/<guid>/download
# ---------------------------------------------------------------------------

def test_download_backup(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can download a completed backup as a .tar.gz archive."""
    _ensure_currency(app)
    client, token = api_admin_client
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        cr = backup_service.create_backup(
            name='Download test', segment_types=['currencies'], user=admin,
        )
        bs = cr.backup_set
        for seg in bs.segments:
            backup_service.execute_backup_segment(seg)
        bs.status = 'completed'
        bs.completed_segments = bs.segments.count()
        db.session.commit()
        guid = str(bs.guid)

    resp = client.get(f'/apis/backups/{guid}/download', headers=_api_headers(token))
    assert resp.status_code == 200
    assert resp.content_type in ('application/gzip', 'application/x-tar',
                                 'application/octet-stream')


# ---------------------------------------------------------------------------
# POST /apis/backups/import
# ---------------------------------------------------------------------------

def test_import_backup_no_file(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Calling /import without a file returns 400."""
    client, token = api_admin_client
    resp = client.post(
        '/apis/backups/import',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        },
    )
    assert resp.status_code == 400


def test_import_backup_roundtrip(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """A backup exported via the service can be imported via the API endpoint."""
    _ensure_currency(app)
    client, token = api_admin_client
    # Create + execute a real backup via service layer
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        cr = backup_service.create_backup(
            name='API import roundtrip', segment_types=['currencies'], user=admin,
        )
        bs = cr.backup_set
        for seg in bs.segments:
            backup_service.execute_backup_segment(seg)
        bs.status = 'completed'
        bs.completed_segments = bs.segments.count()
        db.session.commit()

        export_result = backup_service.export_backup(str(bs.guid))
    assert export_result.success

    resp = client.post(
        '/apis/backups/import',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        },
        data={'archive': (io.BytesIO(export_result.archive_bytes), 'backup.tar.gz')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'guid' in data
