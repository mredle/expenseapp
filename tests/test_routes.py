# coding=utf-8
"""Route integration tests: redirects, auth, main, event, media, admin, and error handlers."""
from __future__ import annotations

import re

import pytest
from flask.testing import FlaskClient

# =========================================================================
# 1. ANONYMOUS USER REDIRECTS (login_required checks)
# =========================================================================

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
def test_anonymous_redirects(client: FlaskClient, route: str) -> None:
    """Test that @login_required routes correctly redirect anonymous users."""
    response = client.get(route)
    assert response.status_code == 302
    assert '/auth/login' in response.location or '/auth/authenticate_fido2' in response.location


# =========================================================================
# 2. AUTHENTICATION ROUTES (GET, POST Valid, POST Invalid)
# =========================================================================

def test_auth_login_redirects_to_fido(client: FlaskClient) -> None:
    """Test that /auth/login redirects to the FIDO2 authentication page."""
    response = client.get('/auth/login')
    assert response.status_code == 302
    assert response.location == "/auth/authenticate_fido2"


def test_auth_password_login_get(client: FlaskClient) -> None:
    """Test that the password login page renders correctly."""
    response = client.get('/auth/authenticate_password')
    assert response.status_code == 200
    assert b"Sign In" in response.data


def test_auth_password_login_post_invalid(client: FlaskClient) -> None:
    """Test that submitting a wrong password fails validation safely."""
    response = client.post('/auth/authenticate_password', data={
        'username': 'testuser',
        'password': 'WRONG_PASSWORD'
    })
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_auth_register_get(client: FlaskClient) -> None:
    """Test that the registration page renders correctly."""
    response = client.get('/auth/register')
    assert response.status_code == 200


def test_auth_register_post_invalid(client: FlaskClient) -> None:
    """Test form validation catches invalid email formats and regex restrictions."""
    response = client.post('/auth/register', data={
        'username': 'invali dname!',
        'email': 'not-an-email-address',
        'locale': 'en'
    })
    assert response.status_code == 200
    assert b"Invalid email address" in response.data or b"Invalid input" in response.data


def test_logout(auth_client: FlaskClient) -> None:
    """Test that logout redirects to the index page."""
    response = auth_client.get('/auth/logout')
    assert response.status_code == 302
    assert response.location == "/index"


# =========================================================================
# 3. MAIN BLUEPRINT ROUTES
# =========================================================================

def test_root_redirects(client: FlaskClient) -> None:
    """Test that the root URL redirects to /index."""
    response = client.get('/')
    assert response.status_code == 302
    assert response.location == "/index"


def test_index_redirects_to_event_index(auth_client: FlaskClient) -> None:
    """Test that authenticated users are redirected from /index to /event/index."""
    response = auth_client.get('/index')
    assert response.status_code == 302
    assert response.location == "/event/index"


def test_edit_profile_get(auth_client: FlaskClient) -> None:
    """Test GET method for profile editing."""
    response = auth_client.get('/edit_profile')
    assert response.status_code == 200
    assert b"testuser" in response.data


def test_edit_profile_post_invalid(auth_client: FlaskClient) -> None:
    """Test POST method rejects empty required fields."""
    response = auth_client.post('/edit_profile', data={
        'username': '',
        'locale': 'en'
    })
    assert response.status_code == 200
    assert b"This field is required" in response.data or b"required" in response.data


def test_user_profile_loads(auth_client: FlaskClient) -> None:
    """Test that a specific user profile loads using pure black-box navigation."""
    response = auth_client.get('/users')
    assert response.status_code == 200

    html_content = response.data.decode('utf-8')
    match = re.search(r'href="/user/([a-f0-9\-]{36})"', html_content)
    assert match is not None, "Could not find a valid user profile link on the page!"

    user_guid = match.group(1)
    profile_response = auth_client.get(f'/user/{user_guid}')
    assert profile_response.status_code == 200


def test_admin_routes_blocked_for_normal_users(auth_client: FlaskClient) -> None:
    """Test that non-admin users are redirected away from admin pages."""
    response = auth_client.get('/administration')
    assert response.status_code == 302
    assert response.location == "/index"


# =========================================================================
# 4. EVENT BLUEPRINT ROUTES (GET, POST Valid, POST Invalid)
# =========================================================================

def test_event_index_loads(auth_client: FlaskClient) -> None:
    """Test that the event index page loads successfully."""
    response = auth_client.get('/event/index')
    assert response.status_code == 200


def test_event_new_get(auth_client: FlaskClient) -> None:
    """Test GET method for new events."""
    response = auth_client.get('/event/new')
    assert response.status_code == 200


def test_event_new_post_invalid(auth_client: FlaskClient) -> None:
    """Test POST method rejects missing required fields on Event generation."""
    response = auth_client.post('/event/new', data={
        'name': '',
        'description': 'Will fail',
        'date': '2026-01-01',
        'base_currency_id': 1,
        'currency_id': [1],
        'exchange_fee': 2.0
    })
    assert response.status_code == 200
    assert b"This field is required" in response.data or b"required" in response.data


def test_event_creation_and_sub_routes(auth_client: FlaskClient) -> None:
    """Pure black-box test for valid POST creation and sub-route navigation."""
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

    select_response = auth_client.get(f'/event/select_user/{event_guid}')
    assert select_response.status_code == 200

    html_content = select_response.data.decode('utf-8')
    user_id_match = re.search(r'<option value="(\d+)">', html_content)
    assert user_id_match is not None, "Could not find a user in the select dropdown!"

    cookie_response = auth_client.post(f'/event/select_user/{event_guid}', data={
        'user_id': user_id_match.group(1)
    })
    assert cookie_response.status_code == 302

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


def test_deep_event_logic_workflow(auth_client: FlaskClient) -> None:
    """Simulate a full real-world workflow: create event, add friend, log expense, settle."""
    # 1. Create the Event & Get Context Cookie
    auth_client.post('/event/new', data={
        'name': 'Weekend Trip',
        'description': 'Integration Testing',
        'date': '2026-06-01',
        'base_currency_id': 1,
        'currency_id': [1],
        'exchange_fee': 0.0
    })

    event_response = auth_client.get('/event/index')
    html_content = event_response.data.decode('utf-8')
    event_guid_match = re.search(r'href="/event/main/([a-f0-9\-]{36})"', html_content)
    assert event_guid_match is not None, "Could not find the new event on the index!"
    event_guid = event_guid_match.group(1)

    select_response = auth_client.get(f'/event/select_user/{event_guid}')
    admin_id_match = re.search(r'<option value="(\d+)">', select_response.data.decode('utf-8'))
    admin_user_id = admin_id_match.group(1)

    auth_client.post(f'/event/select_user/{event_guid}', data={'user_id': admin_user_id})

    # 2. Add a New User to the Event
    user_response = auth_client.post(f'/event/users/{event_guid}', data={
        'username': 'Alice',
        'email': 'alice@example.com',
        'weighting': 1.0,
        'locale': 'en',
        'about_me': 'A test friend'
    }, follow_redirects=True)

    assert user_response.status_code == 200
    assert b"Alice" in user_response.data

    alice_id_match = re.search(
        r'value="(\d+)">Alice</option>',
        auth_client.get(f'/event/expenses/{event_guid}').data.decode('utf-8')
    )
    assert alice_id_match is not None, "Alice was not added to the form choices!"
    alice_user_id = alice_id_match.group(1)

    # 3. Create a Shared Expense
    expense_response = auth_client.post(f'/event/expenses/{event_guid}', data={
        'currency_id': 1,
        'amount': 150.50,
        'affected_users_id': [admin_user_id, alice_user_id],
        'date': '2026-06-02',
        'description': 'Dinner at the restaurant'
    }, follow_redirects=True)

    assert expense_response.status_code == 200
    assert b"150.5" in expense_response.data
    assert b"Dinner at the restaurant" in expense_response.data

    # 4. Create a Settlement (Paying Alice back)
    settlement_response = auth_client.post(f'/event/settlements/{event_guid}', data={
        'currency_id': 1,
        'recipient_id': alice_user_id,
        'amount': 75.25,
        'description': 'My half of the dinner'
    }, follow_redirects=True)

    assert settlement_response.status_code == 200
    assert b"75.25" in settlement_response.data
    assert b"My half of the dinner" in settlement_response.data

    # 5. Verify the Balance Calculation Matrix
    balance_response = auth_client.get(f'/event/balance/{event_guid}')
    assert balance_response.status_code == 200


# =========================================================================
# 5. MEDIA ROUTES
# =========================================================================

def test_media_404s_for_invalid_file(auth_client: FlaskClient) -> None:
    """Test that requesting a nonexistent media file returns 404."""
    response = auth_client.get('/media/999999')
    assert response.status_code == 404


# =========================================================================
# 6. ADMINISTRATOR ROUTES
# =========================================================================

def test_admin_routes_accessible_for_admins(admin_client: FlaskClient) -> None:
    """Test that an admin can successfully access administration pages."""
    response = admin_client.get('/administration')
    assert response.status_code == 200
    assert b"Administration" in response.data


def test_admin_can_load_new_user_form(admin_client: FlaskClient) -> None:
    """Test that an admin can access the user creation page."""
    response = admin_client.get('/new_user')
    assert response.status_code == 200
    assert b"New User" in response.data


def test_normal_user_blocked_from_new_user_form(auth_client: FlaskClient) -> None:
    """Test that a standard user is kicked out of the user creation page."""
    response = auth_client.get('/new_user')
    assert response.status_code == 302
    assert "/users" in response.location


# =========================================================================
# 7. ERROR HANDLER
# =========================================================================

def test_404_error_handler(client: FlaskClient) -> None:
    """Test that invalid routes return the custom 404 page."""
    response = client.get('/this-route-does-not-exist')
    assert response.status_code == 404
    assert b"Not Found" in response.data


def test_500_error_handler(admin_client: FlaskClient) -> None:
    """Test that the application safely throws the expected exception."""
    with pytest.raises(TypeError):
        admin_client.get('/create_error?key=TYPE_ERROR')