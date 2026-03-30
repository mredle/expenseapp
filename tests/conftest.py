# coding=utf-8
"""Shared pytest fixtures: app, client, auth_client, admin_client, and API helpers."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app, db
from app.models import Currency, Event, EventUser, Expense, Settlement, User
from config import Config


@pytest.fixture(params=['local', 's3'])
def app(request: pytest.FixtureRequest):
    """Create a fresh Flask app instance for testing, looping through storage backends."""
    # Create a secure, isolated temporary directory for this test run
    temp_dir = tempfile.mkdtemp()

    # Pre-create the subfolders so Flask doesn't crash trying to save to missing directories
    os.makedirs(os.path.join(temp_dir, 'tmp'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'img'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'timg'), exist_ok=True)

    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        RATELIMIT_ENABLED = False
        STORAGE_DEFAULT_BACKEND = request.param
        SECRET_KEY = 'this-is-a-very-long-dummy-secret-key-for-testing-purposes'

        # Override paths to use the temp directory instead of /app/static
        STORAGE_LOCAL_PATH = temp_dir
        IMAGE_ROOT_PATH = temp_dir
        IMAGE_TMP_PATH = 'tmp'
        IMAGE_IMG_PATH = 'img'
        IMAGE_TIMG_PATH = 'timg'
        UPLOADS_DEFAULT_DEST = os.path.join(temp_dir, 'tmp')
        UPLOADED_IMAGES_DEST = os.path.join(temp_dir, 'tmp')

    app = create_app(TestConfig)

    with app.app_context():
        yield app

        # Teardown
        db.session.remove()
        db.engine.dispose()

        # Wipe all dummy images, thumbnails, and the temp folders
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    """A test client for the app to simulate browser requests."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """A test client that is already logged in as a regular test user."""
    client = app.test_client()

    username = 'testuser'
    password = 'testpassword'

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, email='test@expenseapp.ch', locale='en')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

    client.post('/auth/authenticate_password', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)

    return client


@pytest.fixture
def admin_client(app):
    """A test client that is logged in as an administrator."""
    client = app.test_client()

    username = 'testadmin'
    password = 'adminpassword'

    with app.app_context():
        admin_user = User.query.filter_by(username=username).first()
        if not admin_user:
            admin_user = User(username=username, email='testadmin@expenseapp.ch', locale='en')
            admin_user.set_password(password)
            admin_user.is_admin = True
            db.session.add(admin_user)
            db.session.commit()

    client.post('/auth/authenticate_password', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)

    return client


# ---------------------------------------------------------------------------
# API test helpers
# ---------------------------------------------------------------------------

def _get_api_token(app: Flask, client: FlaskClient, username: str, password: str) -> str:
    """Create a user (if needed), obtain an API token, and return it."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, email=f'{username}@expenseapp.ch', locale='en')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        token = user.get_token()
        db.session.commit()
        return token


def _api_headers(token: str) -> dict[str, str]:
    """Return common API request headers including bearer auth."""
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


@pytest.fixture
def api_client(app: Flask) -> tuple[FlaskClient, str]:
    """A test client with a regular-user API token.

    Returns a ``(client, token)`` tuple.
    """
    client = app.test_client()
    token = _get_api_token(app, client, 'apiuser', 'apipassword')
    return client, token


@pytest.fixture
def api_admin_client(app: Flask) -> tuple[FlaskClient, str]:
    """A test client with an admin-user API token.

    Returns a ``(client, token)`` tuple.
    """
    client = app.test_client()
    with app.app_context():
        admin = User.query.filter_by(username='apiadmin').first()
        if not admin:
            admin = User(username='apiadmin', email='apiadmin@expenseapp.ch', locale='en')
            admin.set_password('apiadminpassword')
            admin.is_admin = True
            db.session.add(admin)
            db.session.commit()
        token = admin.get_token()
        db.session.commit()
    return client, token


@pytest.fixture
def api_currency(app: Flask) -> Currency:
    """Create a test currency (CHF) and return it."""
    with app.app_context():
        currency = Currency.query.filter_by(code='CHF').first()
        if not currency:
            currency = Currency(
                code='CHF',
                name='Swiss Franc',
                number=756,
                exponent=2,
                inCHF=1.0,
                description='Test currency',
            )
            db.session.add(currency)
            db.session.commit()
        return currency


@pytest.fixture
def api_second_currency(app: Flask) -> Currency:
    """Create a second test currency (EUR) and return it."""
    with app.app_context():
        currency = Currency.query.filter_by(code='EUR').first()
        if not currency:
            currency = Currency(
                code='EUR',
                name='Euro',
                number=978,
                exponent=2,
                inCHF=0.93,
                description='Test currency EUR',
            )
            db.session.add(currency)
            db.session.commit()
        return currency


@pytest.fixture
def api_event(
    app: Flask,
    api_client: tuple[FlaskClient, str],
    api_currency: Currency,
) -> Event:
    """Create a test event with the api_client user as admin and return it."""
    _client, _token = api_client
    with app.app_context():
        user = User.query.filter_by(username='apiuser').first()
        currency = db.session.get(Currency, api_currency.id)
        event = Event(
            name='Test Event',
            date=datetime.now(timezone.utc),
            admin=user,
            base_currency=currency,
            currencies=[currency],
            exchange_fee=2.5,
            fileshare_link='',
        )
        db.session.add(event)
        db.session.flush()

        # Create the admin EventUser
        eu = EventUser(
            username=user.username,
            email=user.email,
            weighting=1.0,
            locale='en',
            user_id=user.id,
        )
        eu.event_id = event.id
        db.session.add(eu)
        db.session.flush()

        event.accountant = eu

        db.session.commit()
        return event
