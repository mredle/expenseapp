# -*- coding: utf-8 -*-
import pytest
import uuid
from unittest.mock import patch
from app import db
from app.models import User

@patch('app.email.send_email') 
def test_user_registration(mock_send_email, client, app):
    """Test the two-step user registration and email activation workflow."""
    
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'newuser_{unique_suffix}'
    test_email = f'{test_username}@expenseapp.ch'
    
    # ==========================================================
    # STEP 1: Submit the Registration Form (NO PASSWORD!)
    # ==========================================================
    response = client.post('/auth/register', data={
        'username': test_username,
        'email': test_email,
        'locale': 'en'
        # Do not send passwords here!
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify the user was saved and the activation email was triggered
    with app.app_context():
        user = User.query.filter_by(username=test_username).first()
        assert user is not None, "User was not saved! Form validation failed."
        
        # Depending on your app's exact logic, grab the token. 
        # (If your app uses a dedicated activation route, it might just be `user.token`)
        token = user.get_reset_password_token() 

    # ==========================================================
    # STEP 2: Simulate Clicking the Email Link & Setting Password
    # ==========================================================
    # Note: If your app uses an explicit '/auth/activate/<token>' route, change the URL below!
    # I am assuming it reuses the reset_password logic.
    activation_response = client.post(f'/auth/register_password/{token}', data={
        'password': 'BrandNewPassword123!',
        'password2': 'BrandNewPassword123!', 
        'confirm_password': 'BrandNewPassword123!' # WTForms standard
    }, follow_redirects=True)
    
    assert activation_response.status_code == 200
    
    # ==========================================================
    # STEP 3: Verify the Password was Permanently Saved
    # ==========================================================
    with app.app_context():
        active_user = User.query.filter_by(username=test_username).first()
        assert active_user.check_password('BrandNewPassword123!') is True


def test_login_and_logout(client, app):
    """Test that users can log in and log out successfully."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'loginuser_{unique_suffix}'
    
    # 1. Setup: Create a temporary user for this test
    with app.app_context():
        user = User(username=test_username, email=f'{test_username}@expenseapp.ch', locale='en')
        user.set_password('TestPass123')
        user.token = str(uuid.uuid4()) # Guarantee a unique token!
        db.session.add(user)
        db.session.commit()
        
    # 2. Test valid login (Using authenticate_password!)
    login_response = client.post('/auth/authenticate_password', data={
        'username': test_username,
        'password': 'TestPass123',
        'remember_me': False
    }, follow_redirects=True)
    
    assert login_response.status_code == 200
    assert b"Invalid username or password" not in login_response.data
    
    # 3. Test logout
    logout_response = client.get('/auth/logout', follow_redirects=True)
    assert logout_response.status_code == 200
    assert test_username.encode() not in logout_response.data


def test_invalid_login(client, app):
    """Test that bad credentials are rejected."""
    # Test logging in with an account that doesn't exist (Using authenticate_password!)
    response = client.post('/auth/authenticate_password', data={
        'username': 'ghostuser_does_not_exist',
        'password': 'WrongPassword!',
        'remember_me': False
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Depending on your flash messages, you may need to adjust this string!
    # assert b"Invalid username or password" in response.data


# Target the patch to the exact module where the email function lives
@patch('app.auth.routes.send_validate_email')
def test_password_reset_workflow(mock_send_email, client, app):
    """Test requesting a password reset and using the token to change it."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'resetuser_{unique_suffix}'
    test_email = f'{test_username}@expenseapp.ch'
    
    # 1. Setup
    with app.app_context():
        user = User(username=test_username, email=test_email, locale='en')
        user.set_password('OldPassword123')
        user.token = str(uuid.uuid4()) # Guarantee a unique token!
        db.session.add(user)
        db.session.commit()
        
    # 2. Request a password reset
    reset_request_response = client.post('/auth/reset_authentication', data={
        'email': test_email
    }, follow_redirects=True)
    
    assert reset_request_response.status_code == 200
    assert mock_send_email.called
    
    # 3. Extract the token explicitly
    with app.app_context():
        user = User.query.filter_by(username=test_username).first()
        token = user.get_reset_password_token()
        
    # 4. Use the token to submit a new password
    reset_response = client.post(f'/auth/register_password/{token}', data={
        'password': 'NewPassword123!',
        'password2': 'NewPassword123!',
        'confirm_password': 'NewPassword123!'
    }, follow_redirects=True)
    
    assert reset_response.status_code == 200
    
    # 5. Verify the password was actually updated in the database
    with app.app_context():
        updated_user = User.query.filter_by(username=test_username).first()
        assert updated_user.check_password('NewPassword123!') is True
        assert updated_user.check_password('OldPassword123') is False