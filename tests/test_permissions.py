# -*- coding: utf-8 -*-
import pytest
from datetime import datetime, timezone
from app import db
from app.models import User, Event, Currency, EventUser

# =========================================================================
# THE PERMISSION MATRIX
# Format: (URL_TEMPLATE, METHOD, ANON_CODE, USER_CODE, ADMIN_CODE)
# =========================================================================
ROUTES = [
    # 1. AUTH ROUTES (Logged out = 200, Logged in = 302 Redirect to Index)
    ('/auth/authenticate_password', 'GET', 200, 302, 302),
    ('/auth/register', 'GET', 200, 302, 302),
    ('/auth/reset_authentication', 'GET', 200, 302, 302),
    
    # 2. STANDARD PROTECTED ROUTES (Anon = 302 Redirect, User = 200, Admin = 200)
    ('/event/index', 'GET', 302, 200, 200),
    ('/event/new', 'GET', 302, 200, 200),
    ('/event/new', 'POST', 302, 200, 200), # Empty POST fails validation, returning 200 form
    ('/users', 'GET', 302, 200, 200),
    ('/currencies', 'GET', 302, 200, 200),
    ('/edit_profile', 'GET', 302, 200, 200),
    ('/messages', 'GET', 302, 200, 200),
    ('/statistics', 'GET', 302, 200, 200),
    
    # 3. ADMIN-ONLY ROUTES (Anon = 302, User = 302 Redirect to Index/Users, Admin = 200)
    ('/administration', 'GET', 302, 302, 200),
    ('/new_user', 'GET', 302, 302, 200),
    ('/new_user', 'POST', 302, 302, 200), # Empty POST
    ('/new_currency', 'GET', 302, 302, 200),
    ('/new_currency', 'POST', 302, 302, 200),
    
    # 4. DYNAMIC ROUTES (GUIDs will be injected dynamically by the fixture)
    ('/user/{user_guid}', 'GET', 302, 200, 200),
    ('/edit_user/{user_guid}', 'GET', 302, 302, 200),
    ('/edit_currency/{currency_guid}', 'GET', 302, 302, 200),
    ('/event/select_user/{event_guid}', 'GET', 200, 200, 200),
    # Note: Accessing event/main requires the user cookie to be set, which is handled in deeper tests
]

@pytest.fixture
def dummy_guids(app):
    """Creates a guaranteed set of dummy data to generate valid GUIDs for the test URLs."""
    with app.app_context():
        # Ensure an admin exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@expenseapp.local', is_admin=True)
            db.session.add(admin)
            
        # Ensure a normal user exists
        user = User.query.filter_by(username='testuser').first()
        if not user:
            user = User(username='testuser', email='testuser@expenseapp.local', is_admin=False)
            db.session.add(user)
            
        # Grab the CHF currency seeded by your run_tests.sh script
        currency = Currency.query.filter_by(code='CHF').first()
        
        # Create an event and add our test user to it
        event = Event(
            name="Permission Matrix Event", 
            base_currency=currency, 
            admin=user,
            date=datetime.now(timezone.utc),
            currencies=[currency],
            exchange_fee=0.0,
            fileshare_link=""
        )
        
        event_user = EventUser(
            username=user.username, 
            email=user.email,
            weighting=1.0,  # Standard default weighting
            locale='en'     # Standard default locale
        )
        
        event.add_user(event_user)
        db.session.add(event)
        
        db.session.commit()
        
        return {
            'user_guid': user.guid,
            'admin_guid': admin.guid,
            'currency_guid': currency.guid,
            'event_guid': event.guid
        }


# =========================================================================
# 1. TEST ANONYMOUS ACCESS
# =========================================================================
@pytest.mark.parametrize("url_template, method, anon_code, user_code, admin_code", ROUTES)
def test_anonymous_access(client, dummy_guids, url_template, method, anon_code, user_code, admin_code):
    """Test that unauthenticated users are correctly redirected or allowed."""
    url = url_template.format(**dummy_guids)
    
    if method == 'GET':
        resp = client.get(url, follow_redirects=False)
    else:
        resp = client.post(url, data={}, follow_redirects=False) # Blank POST
        
    assert resp.status_code == anon_code, f"Anonymous {method} to {url} expected {anon_code} but got {resp.status_code}"
    
    # Verify exact redirect targets for anonymous users!
    if anon_code == 302:
        assert 'authenticate' in resp.location or 'login' in resp.location, f"Anonymous user not redirected to auth from {url}"

# =========================================================================
# 2. TEST NORMAL USER ACCESS
# =========================================================================
@pytest.mark.parametrize("url_template, method, anon_code, user_code, admin_code", ROUTES)
def test_normal_user_access(auth_client, dummy_guids, url_template, method, anon_code, user_code, admin_code):
    """Test that standard logged-in users have correct permissions."""
    url = url_template.format(**dummy_guids)
    
    if method == 'GET':
        resp = auth_client.get(url, follow_redirects=False)
    else:
        resp = auth_client.post(url, data={}, follow_redirects=False) # Blank POST
        
    assert resp.status_code == user_code, f"Normal User {method} to {url} expected {user_code} but got {resp.status_code}"

# =========================================================================
# 3. TEST ADMIN USER ACCESS
# =========================================================================
@pytest.mark.parametrize("url_template, method, anon_code, user_code, admin_code", ROUTES)
def test_admin_access(admin_client, dummy_guids, url_template, method, anon_code, user_code, admin_code):
    """Test that administrators have unrestricted access."""
    url = url_template.format(**dummy_guids)
    
    if method == 'GET':
        resp = admin_client.get(url, follow_redirects=False)
    else:
        resp = admin_client.post(url, data={}, follow_redirects=False) # Blank POST
        
    assert resp.status_code == admin_code, f"Admin User {method} to {url} expected {admin_code} but got {resp.status_code}"