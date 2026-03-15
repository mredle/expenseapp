# -*- coding: utf-8 -*-

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
    print(response.location)
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
    print(response.location)