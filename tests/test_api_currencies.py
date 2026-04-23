# coding=utf-8
"""Tests for the Currencies REST API namespace (/apis/currencies/)."""

from __future__ import annotations

import json
import uuid

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import Currency
from tests.conftest import _api_headers


# ---------------------------------------------------------------------------
# GET /apis/currencies/ (list)
# ---------------------------------------------------------------------------


def test_list_currencies_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_currency: Currency,
) -> None:
    """Authenticated user can list currencies and receives paginated results."""
    client, token = api_client
    resp = client.get('/apis/currencies/?per_page=200', headers=_api_headers(token))

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data
    assert 'has_next' in data
    assert 'has_prev' in data
    assert data['total'] >= 1
    codes = [item['code'] for item in data['items']]
    assert 'CHF' in codes


def test_list_currencies_requires_auth(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Listing currencies without a bearer token returns 401."""
    resp = client.get('/apis/currencies/', headers={'Accept': 'application/json'})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /apis/currencies/ (create)
# ---------------------------------------------------------------------------


def test_create_currency_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Admin can create a new currency and receives 201 with the resource."""
    client, token = api_admin_client
    code = f'T{uuid.uuid4().hex[:3].upper()}'
    payload = {
        'code': code,
        'name': f'Test Currency {code}',
        'number': 999,
        'exponent': 2,
        'inCHF': 1.23,
        'description': 'Created by test',
    }
    resp = client.post(
        '/apis/currencies/',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['code'] == code
    assert data['name'] == payload['name']
    assert data['guid']

    # Verify persisted in DB
    with app.app_context():
        currency = Currency.query.filter_by(code=code).first()
        assert currency is not None
        assert currency.number == 999


def test_create_currency_non_admin(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Regular (non-admin) user receives 403 when creating a currency."""
    client, token = api_client
    code = f'T{uuid.uuid4().hex[:3].upper()}'
    payload = {
        'code': code,
        'name': f'Test Currency {code}',
        'number': 111,
        'exponent': 2,
        'inCHF': 0.50,
        'description': '',
    }
    resp = client.post(
        '/apis/currencies/',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 403


def test_create_currency_missing_fields(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
) -> None:
    """Creating a currency with missing required fields returns 400."""
    client, token = api_admin_client
    # Omit 'code' and 'number' — only send partial data
    payload = {
        'name': 'Incomplete Currency',
        'exponent': 2,
        'inCHF': 1.0,
    }
    resp = client.post(
        '/apis/currencies/',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 400


def test_create_currency_requires_auth(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Creating a currency without a bearer token returns 401."""
    payload = {
        'code': 'XYZ',
        'name': 'No Auth Currency',
        'number': 888,
        'exponent': 2,
        'inCHF': 0.99,
        'description': '',
    }
    resp = client.post(
        '/apis/currencies/',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        data=json.dumps(payload),
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /apis/currencies/<guid> (read single)
# ---------------------------------------------------------------------------


def test_get_currency_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_currency: Currency,
) -> None:
    """Authenticated user can retrieve a single currency by GUID."""
    client, token = api_client

    with app.app_context():
        currency = db.session.get(Currency, api_currency.id)
        guid = str(currency.guid)

    resp = client.get(
        f'/apis/currencies/{guid}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == guid
    assert data['code'] == 'CHF'
    assert data['name'] == 'Swiss Franc'


def test_get_currency_not_found(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Requesting a non-existent currency GUID returns 404."""
    client, token = api_client
    fake_guid = uuid.uuid4().hex

    resp = client.get(
        f'/apis/currencies/{fake_guid}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /apis/currencies/<guid> (update)
# ---------------------------------------------------------------------------


def test_update_currency_success(
    app: Flask,
    api_admin_client: tuple[FlaskClient, str],
    api_currency: Currency,
) -> None:
    """Admin can update an existing currency."""
    client, token = api_admin_client

    with app.app_context():
        currency = db.session.get(Currency, api_currency.id)
        guid = str(currency.guid)

    updated_name = f'Swiss Franc {uuid.uuid4().hex[:8]}'
    payload = {
        'code': 'CHF',
        'name': updated_name,
        'number': 756,
        'exponent': 2,
        'inCHF': 1.0,
        'description': 'Updated by test',
    }
    resp = client.put(
        f'/apis/currencies/{guid}',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == updated_name
    assert data['description'] == 'Updated by test'

    # Verify persisted in DB
    with app.app_context():
        currency = Currency.query.filter_by(guid=guid).first()
        assert currency is not None
        assert currency.name == updated_name


def test_update_currency_non_admin(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_currency: Currency,
) -> None:
    """Regular (non-admin) user receives 403 when updating a currency."""
    client, token = api_client

    with app.app_context():
        currency = db.session.get(Currency, api_currency.id)
        guid = str(currency.guid)

    payload = {
        'code': 'CHF',
        'name': 'Should Not Update',
        'number': 756,
        'exponent': 2,
        'inCHF': 1.0,
        'description': '',
    }
    resp = client.put(
        f'/apis/currencies/{guid}',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 403
