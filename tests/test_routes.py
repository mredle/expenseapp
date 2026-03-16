# -*- coding: utf-8 -*-

import re
import pytest

# =========================================================================
# 1. ANONYMOUS USER REDIRECTS (login_required checks)
# =========================================================================

# This magical decorator runs this single function 11 times for each route!
@pytest.mark.parametrize("route", [
    '/currencies',
    '/users',
    '/statistics',
    '/messages',
    '/edit_profile',
    '/administration',
    '/logs',
    '/tasks',
    '/event/index',
    '/event/new',
    '/export_posts'
])
def test_anonymous_redirects(client, route):
    """Test that @login_required routes correctly redirect anonymous users."""
    response = client.get(route)
    assert response.status_code == 302
    # They should be bounced to either the login or FIDO page
    assert '/auth/login' in response.location or '/auth/authenticate_fido2' in response.location

# =========================================================================
# 2. AUTHENTICATION ROUTES (GET, POST Valid, POST Invalid)
# =========================================================================

def test_auth_login_redirects_to_fido(client):
    response = client.get('/auth/login')
    assert response.status_code == 302
    assert response.location == "/auth/authenticate_fido2"

def test_auth_password_login_get(client):
    response = client.get('/auth/authenticate_password')
    assert response.status_code == 200
    assert b"Sign In" in response.data

def test_auth_password_login_post_invalid(client):
    """Test that submitting a wrong password fails validation safely."""
    response = client.post('/auth/authenticate_password', data={
        'username': 'testuser',
        'password': 'WRONG_PASSWORD'
    })
    # Status code 200 means the form re-rendered with validation errors
    assert response.status_code == 200 
    assert b"Invalid username or password" in response.data

def test_auth_register_get(client):
    response = client.get('/auth/register')
    assert response.status_code == 200

def test_auth_register_post_invalid(client):
    """Test form validation catches invalid email formats and regex restrictions."""
    response = client.post('/auth/register', data={
        'username': 'invali dname!', # Spaces not allowed by your regex
        'email': 'not-an-email-address', # Invalid email
        'locale': 'en'
    })
    assert response.status_code == 200
    # WTForms should inject error messages into the HTML
    assert b"Invalid email address" in response.data or b"Invalid input" in response.data

def test_logout(auth_client):
    response = auth_client.get('/auth/logout')
    assert response.status_code == 302
    assert response.location == "/index"

# =========================================================================
# 3. MAIN BLUEPRINT ROUTES
# =========================================================================

def test_root_redirects(client):
    response = client.get('/')
    assert response.status_code == 302
    assert response.location == "/index"

def test_index_redirects_to_event_index(auth_client):
    response = auth_client.get('/index')
    assert response.status_code == 302
    assert response.location == "/event/index"

def test_edit_profile_get(auth_client):
    """Test GET method for profile editing."""
    response = auth_client.get('/edit_profile')
    assert response.status_code == 200
    assert b"testuser" in response.data

def test_edit_profile_post_invalid(auth_client):
    """Test POST method rejects empty required fields."""
    response = auth_client.post('/edit_profile', data={
        'username': '', # Missing required field
        'locale': 'en'
    })
    assert response.status_code == 200
    assert b"This field is required" in response.data or b"required" in response.data

def test_user_profile_loads(auth_client):
    """Test that a specific user profile loads using pure black-box navigation."""
    response = auth_client.get('/users')
    assert response.status_code == 200
    
    html_content = response.data.decode('utf-8')
    match = re.search(r'href="/user/([a-f0-9\-]{36})"', html_content)
    assert match is not None, "Could not find a valid user profile link on the page!"
    
    user_guid = match.group(1)
    profile_response = auth_client.get(f'/user/{user_guid}')
    assert profile_response.status_code == 200

def test_admin_routes_blocked_for_normal_users(auth_client):
    response = auth_client.get('/administration')
    assert response.status_code == 302
    assert response.location == "/index"

# =========================================================================
# 4. EVENT BLUEPRINT ROUTES (GET, POST Valid, POST Invalid)
# =========================================================================

def test_event_index_loads(auth_client):
    response = auth_client.get('/event/index')
    assert response.status_code == 200

def test_event_new_get(auth_client):
    """Test GET method for new events."""
    response = auth_client.get('/event/new')
    assert response.status_code == 200

def test_event_new_post_invalid(auth_client):
    """Test POST method rejects missing required fields on Event generation."""
    response = auth_client.post('/event/new', data={
        'name': '', # Missing required name!
        'description': 'Will fail',
        'date': '2026-01-01',
        'base_currency_id': 1,
        'currency_id': [1],
        'exchange_fee': 2.0
    })
    assert response.status_code == 200
    # Make sure the form kicks it back
    assert b"This field is required" in response.data or b"required" in response.data

def test_event_creation_and_sub_routes(auth_client):
    """Pure Black-Box Test for Valid POST Creation and Sub-route navigation."""
    
    # 1. Valid POST creation
    response = auth_client.post('/event/new', data={
        'name': 'Pure Black Box Event',
        'description': 'Testing without DB queries',
        'date': '2026-01-01',
        'base_currency_id': 1,
        'currency_id': [1, 2, 3],
        'exchange_fee': 2.0
    })

    assert response.status_code == 302
    event_guid = response.location.split('/')[-1] 
    
    # 2. Get Cookie Context
    select_response = auth_client.get(f'/event/select_user/{event_guid}')
    assert select_response.status_code == 200
    
    html_content = select_response.data.decode('utf-8')
    user_id_match = re.search(r'<option value="(\d+)">', html_content)
    assert user_id_match is not None, "Could not find a user in the select dropdown!"
    
    cookie_response = auth_client.post(f'/event/select_user/{event_guid}', data={
        'user_id': user_id_match.group(1)
    })
    assert cookie_response.status_code == 302

    # 3. Test Sub-routes (GET)
    routes_to_test = [
        f'/event/main/{event_guid}',
        f'/event/users/{event_guid}',
        f'/event/currencies/{event_guid}',
        f'/event/expenses/{event_guid}',
        f'/event/settlements/{event_guid}',
        f'/event/balance/{event_guid}'
    ]
    
    for route in routes_to_test:
        res = auth_client.get(route)
        assert res.status_code == 200, f"Failed to load {route}"

def test_deep_event_logic_workflow(auth_client):
    """
    Pure Black-Box Integration Test:
    Simulates a full real-world workflow: Creating an event, adding a friend, 
    logging a shared expense, and making a settlement payment.
    """
    # ---------------------------------------------------------
    # 1. Create the Event & Get Context Cookie
    # ---------------------------------------------------------
    auth_client.post('/event/new', data={
        'name': 'Weekend Trip',
        'description': 'Integration Testing',
        'date': '2026-06-01',
        'base_currency_id': 1,
        'currency_id': [1],
        'exchange_fee': 0.0
    })
    
    # Extract GUID from the redirect
    event_response = auth_client.get('/event/index')
    html_content = event_response.data.decode('utf-8')
    event_guid_match = re.search(r'href="/event/main/([a-f0-9\-]{36})"', html_content)
    assert event_guid_match is not None, "Could not find the new event on the index!"
    event_guid = event_guid_match.group(1)
    
    # Get Admin User ID & Cookie
    select_response = auth_client.get(f'/event/select_user/{event_guid}')
    admin_id_match = re.search(r'<option value="(\d+)">', select_response.data.decode('utf-8'))
    admin_user_id = admin_id_match.group(1)
    
    auth_client.post(f'/event/select_user/{event_guid}', data={'user_id': admin_user_id})

    # ---------------------------------------------------------
    # 2. Add a New User to the Event
    # ---------------------------------------------------------
    user_response = auth_client.post(f'/event/users/{event_guid}', data={
        'username': 'Alice',
        'email': 'alice@example.com',
        'weighting': 1.0,
        'locale': 'en',
        'about_me': 'A test friend'
    }, follow_redirects=True)
    
    assert user_response.status_code == 200
    assert b"Alice" in user_response.data
    
    # Extract Alice's dynamic User ID from the DOM so we can use it in the expense
    alice_id_match = re.search(r'value="(\d+)">Alice</option>', auth_client.get(f'/event/expenses/{event_guid}').data.decode('utf-8'))
    assert alice_id_match is not None, "Alice was not added to the form choices!"
    alice_user_id = alice_id_match.group(1)

    # ---------------------------------------------------------
    # 3. Create a Shared Expense
    # ---------------------------------------------------------
    expense_response = auth_client.post(f'/event/expenses/{event_guid}', data={
        'currency_id': 1,
        'amount': 150.50,
        'affected_users_id': [admin_user_id, alice_user_id], # Split between both users
        'date': '2026-06-02',
        'description': 'Dinner at the restaurant'
    }, follow_redirects=True)
    
    assert expense_response.status_code == 200
    assert b"150.5" in expense_response.data
    assert b"Dinner at the restaurant" in expense_response.data

    # ---------------------------------------------------------
    # 4. Create a Settlement (Paying Alice back)
    # ---------------------------------------------------------
    settlement_response = auth_client.post(f'/event/settlements/{event_guid}', data={
        'currency_id': 1,
        'recipient_id': alice_user_id,
        'amount': 75.25,
        'description': 'My half of the dinner'
    }, follow_redirects=True)
    
    assert settlement_response.status_code == 200
    assert b"75.25" in settlement_response.data
    assert b"My half of the dinner" in settlement_response.data

    # ---------------------------------------------------------
    # 5. Verify the Balance Calculation Matrix
    # ---------------------------------------------------------
    # Loading the balance page triggers all the complex math in event.calculate_balance()
    balance_response = auth_client.get(f'/event/balance/{event_guid}')
    assert balance_response.status_code == 200


# =========================================================================
# 5. MEDIA ROUTES
# =========================================================================

def test_media_404s_for_invalid_file(auth_client):
    response = auth_client.get('/media/999999')
    assert response.status_code == 404

# =========================================================================
# 6. ADMINISTRATOR ROUTES
# =========================================================================

def test_admin_routes_accessible_for_admins(admin_client):
    """Test that an admin can successfully access administration pages."""
    response = admin_client.get('/administration')
    assert response.status_code == 200
    assert b"Administration" in response.data

def test_admin_can_load_new_user_form(admin_client):
    """Test that an admin can access the user creation page."""
    response = admin_client.get('/new_user')
    assert response.status_code == 200
    assert b"New User" in response.data

def test_normal_user_blocked_from_new_user_form(auth_client):
    """Test that a standard user is kicked out of the user creation page."""
    response = auth_client.get('/new_user')
    # Should redirect (302) them away
    assert response.status_code == 302
    assert "/users" in response.location

# =========================================================================
# 7. ERROR HANDLER
# =========================================================================

def test_404_error_handler(client):
    """Test that invalid routes return the custom 404 page."""
    response = client.get('/this-route-does-not-exist')
    assert response.status_code == 404
    assert b"Not Found" in response.data # Change to your actual 404 template text

def test_500_error_handler(admin_client):
    """Test that the application safely throws the expected exception."""
    # Because we are using admin_client, we don't need app context blocks here!
    import pytest
    with pytest.raises(TypeError):
        admin_client.get('/create_error?key=TYPE_ERROR')