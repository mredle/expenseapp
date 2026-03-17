# -*- coding: utf-8 -*-


import pytest
from app import create_app, db
from app.models import User
from config import Config

class TestConfig(Config):
    """Inherits everything from config.py, but overrides specific test flags."""
    TESTING = True
    WTF_CSRF_ENABLED = False # Disable CSRF tokens to make form testing much easier
    #STORAGE_DEFAULT_BACKEND = 'local'
    RATELIMIT_ENABLED = False


@pytest.fixture
def app():
    """Creates a fresh Flask app instance for testing."""
    # Pass test-specific configuration
    app = create_app(TestConfig)

    with app.app_context():
        # Create all tables before the test runs
        #db.create_all()
        yield app
        # Drop all tables after the test finishes to leave a clean slate
        #db.session.remove()
        #db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app to simulate browser requests."""
    return app.test_client()

@pytest.fixture
def auth_client(client, app):
    """A test client that is already logged in as a test user."""
    username = 'testuser'
    password = 'testpassword'

    with app.app_context():
        # Check if testuser already exists so we don't crash on the 2nd test
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, email='test@expenseapp.local', locale='en')
            user.set_password(password)
            user.token = 'user_unique_token_123'
            db.session.add(user)
            db.session.commit()

    # Simulate logging in using the correct endpoint and form fields!
    client.post('/auth/authenticate_password', data={
        'username': username,
        'password': password
    }, follow_redirects=True)
    
    return client

@pytest.fixture
def admin_client(client, app):
    """A test client that is logged in as an administrator."""
    username = 'testadmin'
    password = 'adminpassword'

    with app.app_context():
        # Check if the test admin already exists
        admin_user = User.query.filter_by(username=username).first()
        if not admin_user:
            admin_user = User(username=username, email='testadmin@expenseapp.local', locale='en')
            admin_user.set_password(password)
            admin_user.is_admin = True
            admin_user.token = 'admin_unique_token_123'
            db.session.add(admin_user)
            db.session.commit()

    # Simulate logging in as the admin
    client.post('/auth/authenticate_password', data={
        'username': username,
        'password': password
    }, follow_redirects=True)
    
    return client