# -*- coding: utf-8 -*-
"""Shared pytest fixtures: app, client, auth_client, admin_client."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from app import create_app, db
from app.models import User
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
