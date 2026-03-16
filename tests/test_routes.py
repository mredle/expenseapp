# -*- coding: utf-8 -*-

import re

def test_homepage_redirects_1(client):
    """Test that the homepage redirects for anonymous users."""
    response = client.get('/')
    assert response.status_code == 302
    assert response.location == "/index"

def test_homepage_redirects_2(client):
    """Test that the homepage redirects for anonymous users."""
    response = client.get('/index')
    assert response.status_code == 302
    assert response.location == "/event/index"

def test_homepage_redirects_3(client):
    """Test that the homepage redirects for anonymous users."""
    response = client.get('/event/index')
    assert response.status_code == 302
    assert response.location == "/auth/login?next=%2Fevent%2Findex"

def test_login_loads(client):
    """Test that the homepage loads login page for anonymous users."""
    response = client.get('/auth/authenticate_fido2')
    assert response.status_code == 200
    assert b"Sign In" in response.data # Check for specific HTML text

def test_dashboard_loads_for_authenticated_users(auth_client):
    """Test that logged-in users can access the dashboard."""
    response = auth_client.get('/event/index')
    assert response.status_code == 200

def test_create_event(auth_client):
    """Test submitting a form to create a new event."""
    response = auth_client.post('/event/new', data={
        'name': 'Summer Vacation',
        'description': 'Trip to Italy',
        'date': '2026-01-01',
        'base_currency_id': "1",
        'currency_id': ["1", "2", "3"],
        'exchange_fee': "2.0"
    }, follow_redirects=False)
    
    assert response.status_code == 302



# =========================================================================
# 1. AUTHENTICATION ROUTES
# =========================================================================

def test_auth_login_redirects_to_fido(client):
    """Test that the base login route redirects to the FIDO2 page."""
    response = client.get('/auth/login')
    assert response.status_code == 302
    assert response.location == "/auth/authenticate_fido2"

def test_auth_password_login_loads(client):
    """Test that the password login page renders."""
    response = client.get('/auth/authenticate_password')
    assert response.status_code == 200
    assert b"Sign In" in response.data

def test_auth_register_loads(client):
    """Test that the registration page renders."""
    response = client.get('/auth/register')
    assert response.status_code == 200

def test_logout(auth_client):
    """Test that logging out redirects to the index."""
    response = auth_client.get('/auth/logout')
    assert response.status_code == 302
    assert response.location == "/index"

# =========================================================================
# 2. MAIN BLUEPRINT ROUTES (Static)
# =========================================================================

def test_root_redirects(client):
    """Test that the root route redirects to index."""
    response = client.get('/')
    assert response.status_code == 302
    assert response.location == "/index"

def test_index_redirects_to_event_index(auth_client):
    """Test that index redirects authenticated users to the event dashboard."""
    response = auth_client.get('/index')
    assert response.status_code == 302
    assert response.location == "/event/index"

def test_currencies_page(auth_client):
    """Test that the currencies list loads."""
    response = auth_client.get('/currencies')
    assert response.status_code == 200

def test_users_page(auth_client):
    """Test that the users list loads."""
    response = auth_client.get('/users')
    assert response.status_code == 200

def test_statistics_page(auth_client):
    """Test that the statistics page loads."""
    response = auth_client.get('/statistics')
    assert response.status_code == 200

def test_messages_page(auth_client):
    """Test that the messages page loads."""
    response = auth_client.get('/messages')
    assert response.status_code == 200

# =========================================================================
# 3. MAIN BLUEPRINT ROUTES (Dynamic GUIDs & Permissions)
# =========================================================================

def test_user_profile_loads(auth_client):
    """Test that a specific user profile loads using pure black-box navigation."""
    
    # 1. Load the users directory page
    response = auth_client.get('/users')
    assert response.status_code == 200
    
    # 2. Extract a dynamic user GUID straight out of the HTML links
    html_content = response.data.decode('utf-8')
    match = re.search(r'href="/user/([a-f0-9\-]{36})"', html_content)
    assert match is not None, "Could not find a valid user profile link on the page!"
    
    user_guid = match.group(1)
    
    # 3. Test that the specific profile page loads successfully
    profile_response = auth_client.get(f'/user/{user_guid}')
    assert profile_response.status_code == 200

def test_admin_routes_blocked_for_normal_users(auth_client):
    """Test that non-admins cannot access administration pages."""
    response = auth_client.get('/administration')
    # Because 'testuser' is not an admin, they should get a flash message and be redirected
    assert response.status_code == 302

# =========================================================================
# 4. EVENT BLUEPRINT ROUTES
# =========================================================================

def test_event_index_loads(auth_client):
    """Test that the main event dashboard loads."""
    response = auth_client.get('/event/index')
    assert response.status_code == 200

def test_event_creation_and_sub_routes(auth_client):
    """
    Pure Black-Box Test:
    Creates an event, extracts the GUID from the redirect, navigates to the 
    user selection page to organically get the session cookie, and tests all routes.
    """
    
    # 1. Create the event
    # (Note: We are not using follow_redirects=True here so we can catch the 302 response)
    response = auth_client.post('/event/new', data={
        'name': 'Pure Black Box Event',
        'description': 'Testing without DB queries',
        'date': '2026-01-01',
        'base_currency_id': 1,
        'currency_id': [1, 2, 3],
        'exchange_fee': 2.0
    })

    # 2. Extract Event GUID directly from the redirect location header!
    # The location header will look like: "/event/main/1234-5678-90ab..."
    assert response.status_code == 302
    redirect_url = response.location
    event_guid = redirect_url.split('/')[-1] 
    
    # 3. Organically acquire the EventUser context cookie
    # Navigate to the select user page
    select_response = auth_client.get(f'/event/select_user/{event_guid}')
    assert select_response.status_code == 200
    
    # Parse the HTML response to find the value of the first user in the dropdown list
    html_content = select_response.data.decode('utf-8')
    user_id_match = re.search(r'<option value="(\d+)">', html_content)
    assert user_id_match is not None, "Could not find a user in the select dropdown!"
    user_id = user_id_match.group(1)

    # Submit the form to select the user. 
    # Flask's test client will automatically store the cookie sent back by the server!
    cookie_response = auth_client.post(f'/event/select_user/{event_guid}', data={
        'user_id': user_id
    })
    assert cookie_response.status_code == 302
    assert cookie_response.location == f"/event/main/{event_guid}"

    # 4. Now the test client automatically holds the cookie natively! Test all sub-routes.
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

# =========================================================================
# 5. MEDIA ROUTES
# =========================================================================

def test_media_404s_for_invalid_file(auth_client):
    """Test that requesting a non-existent file gracefully returns a 404."""
    response = auth_client.get('/media/999999')
    assert response.status_code == 404