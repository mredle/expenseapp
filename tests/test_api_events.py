# coding=utf-8
"""Tests for the Events REST API namespace (/apis/events/)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import Currency, Event, EventUser, Expense, Settlement, User
from tests.conftest import _api_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_ctx(app: Flask, api_event: Event) -> dict:
    """Re-load api_event inside an app context and return common identifiers."""
    with app.app_context():
        event = db.session.get(Event, api_event.id)
        eu = event.users.first()
        return {
            'event_guid': str(event.guid),
            'event_id': event.id,
            'eu_guid': str(eu.guid),
            'eu_id': eu.id,
            'currency_id': event.base_currency_id,
            'currency_guid': str(event.base_currency.guid),
        }


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------


def test_list_events_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list events and receives a paginated response."""
    client, token = api_client
    resp = client.get('/apis/events/', headers=_api_headers(token))

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data
    assert data['total'] >= 1


def test_list_events_requires_auth(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Listing events without a bearer token returns 401."""
    resp = client.get('/apis/events/', headers={'Accept': 'application/json'})

    assert resp.status_code == 401


def test_create_event_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_currency: Currency,
) -> None:
    """Authenticated user can create a new event and receives 201."""
    client, token = api_client
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        currency = db.session.get(Currency, api_currency.id)
        currency_id = currency.id

    payload = {
        'name': f'New Event {suffix}',
        'date': '2025-06-15T10:00:00',
        'base_currency_id': currency_id,
        'currency_ids': [currency_id],
        'exchange_fee': 1.5,
        'fileshare_link': '',
        'description': 'Created by test',
    }
    resp = client.post(
        '/apis/events/',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['name'] == f'New Event {suffix}'
    assert data['guid']

    with app.app_context():
        event = Event.query.filter_by(name=f'New Event {suffix}').first()
        assert event is not None


def test_create_event_missing_fields(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Creating an event with missing required fields returns 400."""
    client, token = api_client
    payload = {
        'name': 'Incomplete Event',
    }
    resp = client.post(
        '/apis/events/',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 400


def test_create_event_requires_auth(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Creating an event without a bearer token returns 401."""
    payload = {
        'name': 'No Auth Event',
        'date': '2025-06-15T10:00:00',
        'base_currency_id': 1,
        'currency_ids': [1],
        'exchange_fee': 0.0,
    }
    resp = client.post(
        '/apis/events/',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        data=json.dumps(payload),
    )

    assert resp.status_code == 401


def test_get_event_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can retrieve a single event by GUID."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == ctx['event_guid']
    assert data['name'] == 'Test Event'


def test_get_event_not_found(
    app: Flask,
    api_client: tuple[FlaskClient, str],
) -> None:
    """Requesting a non-existent event GUID returns 404."""
    client, token = api_client
    fake_guid = uuid.uuid4().hex

    resp = client.get(
        f'/apis/events/{fake_guid}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 404


def test_update_event_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event admin can update an existing event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    payload = {
        'name': f'Updated Event {suffix}',
        'date': '2025-07-01T12:00:00',
        'base_currency_id': ctx['currency_id'],
        'currency_ids': [ctx['currency_id']],
        'exchange_fee': 3.0,
        'accountant_id': ctx['eu_id'],
        'fileshare_link': 'https://example.com',
        'description': 'Updated by test',
    }
    resp = client.put(
        f'/apis/events/{ctx["event_guid"]}',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == f'Updated Event {suffix}'


# ---------------------------------------------------------------------------
# Event Users
# ---------------------------------------------------------------------------


def test_list_event_users_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list event users."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/users',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] >= 1
    assert 'items' in data


def test_add_event_user_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event admin can add a new user to the event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    payload = {
        'username': f'newuser_{suffix}',
        'email': f'newuser_{suffix}@test.ch',
        'weighting': 1.0,
        'locale': 'en',
        'about_me': '',
    }
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/users',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['username'] == f'newuser_{suffix}'
    assert data['guid']


def test_add_event_user_missing_fields(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Adding a user with missing required fields returns 400."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    payload = {
        'username': 'incomplete',
    }
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/users',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 400


def test_add_event_user_permission_denied(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """A non-admin user receives 403 when trying to add an event user."""
    _admin_client, _admin_token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    # Create a second user with their own token
    with app.app_context():
        other = User(
            username=f'other_{suffix}',
            email=f'other_{suffix}@test.ch',
            locale='en',
        )
        other.set_password('pass')
        db.session.add(other)
        db.session.commit()
        other_token = other.get_token()
        db.session.commit()

    other_client = app.test_client()
    payload = {
        'username': f'blocked_{suffix}',
        'email': f'blocked_{suffix}@test.ch',
        'weighting': 1.0,
    }
    resp = other_client.post(
        f'/apis/events/{ctx["event_guid"]}/users',
        headers=_api_headers(other_token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 403


def test_get_event_user_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can retrieve a single event user by GUID."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/users/{ctx["eu_guid"]}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == ctx['eu_guid']
    assert data['username'] == 'apiuser'


def test_remove_event_user_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event admin can remove a user who has no expenses."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    # First add a user (with no expenses)
    payload = {
        'username': f'removeme_{suffix}',
        'email': f'removeme_{suffix}@test.ch',
        'weighting': 1.0,
        'locale': 'en',
    }
    add_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/users',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )
    assert add_resp.status_code == 201
    new_user_guid = add_resp.get_json()['guid']

    # Now remove
    resp = client.delete(
        f'/apis/events/{ctx["event_guid"]}/users/{new_user_guid}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'User removed'


def test_update_event_user_profile_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can update an event user's profile."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    payload = {
        'username': f'updated_{suffix}',
        'email': f'updated_{suffix}@test.ch',
        'weighting': 2.0,
        'about_me': 'Updated profile',
        'locale': 'de',
    }
    resp = client.put(
        f'/apis/events/{ctx["event_guid"]}/users/{ctx["eu_guid"]}/profile',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['username'] == f'updated_{suffix}'
    assert data['weighting'] == 2.0


def test_update_event_user_bank_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can update an event user's bank details."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    payload = {
        'iban': 'CH9300762011623852957',
        'bank': 'UBS',
        'name': 'Test User',
        'address': 'Bahnhofstrasse 1',
        'address_suffix': '',
        'zip_code': 8001,
        'city': 'Zurich',
        'country': 'CH',
    }
    resp = client.put(
        f'/apis/events/{ctx["event_guid"]}/users/{ctx["eu_guid"]}/bank',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == ctx['eu_guid']


# ---------------------------------------------------------------------------
# Event Currencies
# ---------------------------------------------------------------------------


def test_list_event_currencies_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list currencies for an event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/currencies',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] >= 1
    codes = [item['currency_code'] for item in data['items']]
    assert 'CHF' in codes


def test_set_currency_rate_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event admin can set the exchange rate for a currency."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    payload = {'rate': 1.05}
    resp = client.put(
        f'/apis/events/{ctx["event_guid"]}/currencies/{ctx["currency_guid"]}/rate',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'Rate updated'


def test_set_currency_rate_permission_denied(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """A non-admin user receives 403 when setting a currency rate."""
    _admin_client, _admin_token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        other = User(
            username=f'rateother_{suffix}',
            email=f'rateother_{suffix}@test.ch',
            locale='en',
        )
        other.set_password('pass')
        db.session.add(other)
        db.session.commit()
        other_token = other.get_token()
        db.session.commit()

    other_client = app.test_client()
    payload = {'rate': 9.99}
    resp = other_client.put(
        f'/apis/events/{ctx["event_guid"]}/currencies/{ctx["currency_guid"]}/rate',
        headers=_api_headers(other_token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


def test_list_expenses_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list expenses for an event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data


def test_list_expenses_requires_auth(
    app: Flask,
    client: FlaskClient,
    api_event: Event,
) -> None:
    """Listing expenses without a bearer token returns 401."""
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers={'Accept': 'application/json'},
    )

    assert resp.status_code == 401


def test_create_expense_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can create an expense with the X-EventUser-GUID header."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'currency_id': ctx['currency_id'],
        'amount': 42.50,
        'affected_user_ids': [ctx['eu_id']],
        'date': '2025-06-15T12:00:00',
        'description': 'Lunch',
    }
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=headers,
        data=json.dumps(payload),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['amount'] == 42.50
    assert data['guid']


def test_create_expense_missing_fields(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Creating an expense with missing required fields returns 400."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'amount': 10.0,
    }
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=headers,
        data=json.dumps(payload),
    )

    assert resp.status_code == 400


def test_create_expense_requires_eventuser(
    app: Flask,
    api_event: Event,
) -> None:
    """Creating an expense without X-EventUser-GUID header returns 401."""
    suffix = uuid.uuid4().hex[:8]

    # Create a user who is NOT an event participant
    with app.app_context():
        outsider = User(
            username=f'outsider_{suffix}',
            email=f'outsider_{suffix}@test.ch',
            locale='en',
        )
        outsider.set_password('pass')
        db.session.add(outsider)
        db.session.commit()
        outsider_token = outsider.get_token()
        db.session.commit()

        event = db.session.get(Event, api_event.id)
        event_guid = str(event.guid)
        currency_id = event.base_currency_id

    outsider_client = app.test_client()
    payload = {
        'currency_id': currency_id,
        'amount': 10.0,
        'affected_user_ids': [1],
        'date': '2025-06-15T12:00:00',
    }
    resp = outsider_client.post(
        f'/apis/events/{event_guid}/expenses',
        headers=_api_headers(outsider_token),
        data=json.dumps(payload),
    )

    assert resp.status_code == 401


def test_get_expense_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can retrieve a single expense by GUID."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    # Create an expense first
    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'currency_id': ctx['currency_id'],
        'amount': 25.00,
        'affected_user_ids': [ctx['eu_id']],
        'date': '2025-06-15T12:00:00',
        'description': 'Dinner',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    expense_guid = create_resp.get_json()['guid']

    # Now retrieve it
    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/expenses/{expense_guid}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == expense_guid
    assert data['amount'] == 25.00


def test_update_expense_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can update an existing expense."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    # Create an expense
    payload = {
        'currency_id': ctx['currency_id'],
        'amount': 30.00,
        'affected_user_ids': [ctx['eu_id']],
        'date': '2025-06-15T12:00:00',
        'description': 'Original',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    expense_guid = create_resp.get_json()['guid']

    # Update it
    update_payload = {
        'currency_id': ctx['currency_id'],
        'amount': 55.00,
        'affected_user_ids': [ctx['eu_id']],
        'date': '2025-07-01T12:00:00',
        'description': 'Updated expense',
    }
    resp = client.put(
        f'/apis/events/{ctx["event_guid"]}/expenses/{expense_guid}',
        headers=headers,
        data=json.dumps(update_payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['amount'] == 55.00


def test_delete_expense_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can delete an expense."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    # Create an expense
    payload = {
        'currency_id': ctx['currency_id'],
        'amount': 15.00,
        'affected_user_ids': [ctx['eu_id']],
        'date': '2025-06-15T12:00:00',
        'description': 'To be deleted',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    expense_guid = create_resp.get_json()['guid']

    # Delete it
    resp = client.delete(
        f'/apis/events/{ctx["event_guid"]}/expenses/{expense_guid}',
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'Expense removed'


def test_list_expense_users_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list the affected users of an expense."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    # Create an expense with the current user affected
    payload = {
        'currency_id': ctx['currency_id'],
        'amount': 20.00,
        'affected_user_ids': [ctx['eu_id']],
        'date': '2025-06-15T12:00:00',
        'description': 'With users',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/expenses',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    expense_guid = create_resp.get_json()['guid']

    # List affected users
    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/expenses/{expense_guid}/users',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] >= 1


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------


def _add_second_event_user(
    client: FlaskClient,
    token: str,
    event_guid: str,
) -> dict:
    """Add a second event user and return the response JSON."""
    suffix = uuid.uuid4().hex[:8]
    payload = {
        'username': f'recipient_{suffix}',
        'email': f'recipient_{suffix}@test.ch',
        'weighting': 1.0,
        'locale': 'en',
    }
    resp = client.post(
        f'/apis/events/{event_guid}/users',
        headers=_api_headers(token),
        data=json.dumps(payload),
    )
    assert resp.status_code == 201
    return resp.get_json()


def test_list_settlements_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list settlements for an event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data


def test_create_settlement_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can create a settlement (needs two event users)."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    # Add a second user as recipient
    recipient_data = _add_second_event_user(client, token, ctx['event_guid'])
    recipient_id = recipient_data['id']

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'recipient_id': recipient_id,
        'currency_id': ctx['currency_id'],
        'amount': 100.00,
        'description': 'Settlement test',
    }
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=headers,
        data=json.dumps(payload),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['amount'] == 100.00
    assert data['guid']


def test_create_settlement_missing_fields(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Creating a settlement with missing required fields returns 400."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'amount': 50.00,
    }
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=headers,
        data=json.dumps(payload),
    )

    assert resp.status_code == 400


def test_get_settlement_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can retrieve a single settlement by GUID."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    recipient_data = _add_second_event_user(client, token, ctx['event_guid'])

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'recipient_id': recipient_data['id'],
        'currency_id': ctx['currency_id'],
        'amount': 75.00,
        'description': 'Get test',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    settlement_guid = create_resp.get_json()['guid']

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/settlements/{settlement_guid}',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['guid'] == settlement_guid
    assert data['amount'] == 75.00


def test_update_settlement_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can update an existing settlement."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    recipient_data = _add_second_event_user(client, token, ctx['event_guid'])

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'recipient_id': recipient_data['id'],
        'currency_id': ctx['currency_id'],
        'amount': 60.00,
        'description': 'Original settlement',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    settlement_guid = create_resp.get_json()['guid']

    update_payload = {
        'recipient_id': recipient_data['id'],
        'currency_id': ctx['currency_id'],
        'amount': 80.00,
        'description': 'Updated settlement',
    }
    resp = client.put(
        f'/apis/events/{ctx["event_guid"]}/settlements/{settlement_guid}',
        headers=headers,
        data=json.dumps(update_payload),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['amount'] == 80.00


def test_delete_settlement_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can delete a settlement."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    recipient_data = _add_second_event_user(client, token, ctx['event_guid'])

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {
        'recipient_id': recipient_data['id'],
        'currency_id': ctx['currency_id'],
        'amount': 40.00,
        'description': 'To be deleted',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    settlement_guid = create_resp.get_json()['guid']

    resp = client.delete(
        f'/apis/events/{ctx["event_guid"]}/settlements/{settlement_guid}',
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'Settlement removed'


def test_confirm_settlement_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can confirm a draft settlement."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    recipient_data = _add_second_event_user(client, token, ctx['event_guid'])

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    # Create a settlement (defaults to draft=False via service, but
    # we confirm it regardless — the endpoint simply sets draft=False)
    payload = {
        'recipient_id': recipient_data['id'],
        'currency_id': ctx['currency_id'],
        'amount': 50.00,
        'description': 'Draft to confirm',
    }
    create_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements',
        headers=headers,
        data=json.dumps(payload),
    )
    assert create_resp.status_code == 201
    settlement_guid = create_resp.get_json()['guid']

    # Confirm it
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/settlements/{settlement_guid}/confirm',
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['draft'] is False


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


def test_list_posts_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can list posts for an event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/posts',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert 'total' in data


def test_create_post_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can create a post with the X-EventUser-GUID header."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {'body': 'Hello, this is a test post!'}
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/posts',
        headers=headers,
        data=json.dumps(payload),
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['body'] == 'Hello, this is a test post!'
    assert data['guid']


def test_create_post_missing_body(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Creating a post without a body returns 400."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    headers = _api_headers(token)
    headers['X-EventUser-GUID'] = ctx['eu_guid']

    payload = {'body': ''}
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/posts',
        headers=headers,
        data=json.dumps(payload),
    )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------


def test_get_balance_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Authenticated user can retrieve the event balance."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/balance',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert 'balances' in data
    assert 'total_expenses' in data
    assert 'draft_settlements' in data


def test_get_balance_requires_auth(
    app: Flask,
    client: FlaskClient,
    api_event: Event,
) -> None:
    """Retrieving balance without a bearer token returns 401."""
    ctx = _event_ctx(app, api_event)

    resp = client.get(
        f'/apis/events/{ctx["event_guid"]}/balance',
        headers={'Accept': 'application/json'},
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_close_event_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event admin can close an event with no draft settlements."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    # Ensure there are no draft settlements by deleting any existing ones
    with app.app_context():
        event = db.session.get(Event, api_event.id)
        event.settlements.filter_by(draft=True).delete()
        db.session.commit()

    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/close',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'Event closed'

    with app.app_context():
        event = db.session.get(Event, api_event.id)
        assert event.closed is True


def test_close_event_permission_denied(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """A non-admin user receives 403 when closing an event."""
    _admin_client, _admin_token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        other = User(
            username=f'closeother_{suffix}',
            email=f'closeother_{suffix}@test.ch',
            locale='en',
        )
        other.set_password('pass')
        db.session.add(other)
        db.session.commit()
        other_token = other.get_token()
        db.session.commit()

    other_client = app.test_client()
    resp = other_client.post(
        f'/apis/events/{ctx["event_guid"]}/close',
        headers=_api_headers(other_token),
    )

    assert resp.status_code == 403


def test_reopen_event_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event admin can reopen a previously closed event."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    # First, ensure no draft settlements and close the event
    with app.app_context():
        event = db.session.get(Event, api_event.id)
        event.settlements.filter_by(draft=True).delete()
        db.session.commit()

    close_resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/close',
        headers=_api_headers(token),
    )
    assert close_resp.status_code == 200

    # Now reopen
    resp = client.post(
        f'/apis/events/{ctx["event_guid"]}/reopen',
        headers=_api_headers(token),
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'Event reopened'

    with app.app_context():
        event = db.session.get(Event, api_event.id)
        assert event.closed is False


def test_convert_currencies_permission_denied(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """A non-admin user receives 403 when converting currencies."""
    _admin_client, _admin_token = api_client
    ctx = _event_ctx(app, api_event)
    suffix = uuid.uuid4().hex[:8]

    with app.app_context():
        other = User(
            username=f'convother_{suffix}',
            email=f'convother_{suffix}@test.ch',
            locale='en',
        )
        other.set_password('pass')
        db.session.add(other)
        db.session.commit()
        other_token = other.get_token()
        db.session.commit()

    other_client = app.test_client()
    resp = other_client.post(
        f'/apis/events/{ctx["event_guid"]}/convert-currencies',
        headers=_api_headers(other_token),
    )

    assert resp.status_code == 403


def test_request_balance_success(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_event: Event,
) -> None:
    """Event user can request a balance PDF report."""
    client, token = api_client
    ctx = _event_ctx(app, api_event)

    with patch('app.services.event_service.request_balance_pdf') as mock_pdf:
        resp = client.post(
            f'/apis/events/{ctx["event_guid"]}/request-balance',
            headers=_api_headers(token),
            data=json.dumps({}),
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['message'] == 'Balance report queued'
