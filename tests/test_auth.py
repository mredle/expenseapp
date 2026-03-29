# -*- coding: utf-8 -*-
"""Tests for user registration, login/logout, and password reset workflows."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app import db
from app.models import User


@patch('app.email.send_email')
def test_user_registration(mock_send_email, client, app) -> None:
    """Test the two-step user registration and email activation workflow."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'newuser_{unique_suffix}'
    test_email = f'{test_username}@expenseapp.ch'

    # Step 1: Submit the registration form (no password at this stage)
    response = client.post('/auth/register', data={
        'username': test_username,
        'email': test_email,
        'locale': 'en',
    }, follow_redirects=True)

    assert response.status_code == 200

    # Verify the user was saved and the activation email was triggered
    with app.app_context():
        user = User.query.filter_by(username=test_username).first()
        assert user is not None, "User was not saved! Form validation failed."
        token = user.get_reset_password_token()

    # Step 2: Simulate clicking the email link and setting a password
    activation_response = client.post(f'/auth/register_password/{token}', data={
        'password': 'BrandNewPassword123!',
        'password2': 'BrandNewPassword123!',
        'confirm_password': 'BrandNewPassword123!',
    }, follow_redirects=True)

    assert activation_response.status_code == 200

    # Step 3: Verify the password was permanently saved
    with app.app_context():
        active_user = User.query.filter_by(username=test_username).first()
        assert active_user.check_password('BrandNewPassword123!') is True


def test_login_and_logout(client, app) -> None:
    """Test that users can log in and log out successfully."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'loginuser_{unique_suffix}'

    with app.app_context():
        user = User(username=test_username, email=f'{test_username}@expenseapp.ch', locale='en')
        user.set_password('TestPass123')
        user.get_token()
        db.session.add(user)
        db.session.commit()

    login_response = client.post('/auth/authenticate_password', data={
        'username': test_username,
        'password': 'TestPass123',
        'remember_me': False,
    }, follow_redirects=True)

    assert login_response.status_code == 200
    assert b"Invalid username or password" not in login_response.data

    logout_response = client.get('/auth/logout', follow_redirects=True)
    assert logout_response.status_code == 200
    assert test_username.encode() not in logout_response.data


def test_invalid_login(client, app) -> None:
    """Test that bad credentials are rejected."""
    response = client.post('/auth/authenticate_password', data={
        'username': 'ghostuser_does_not_exist',
        'password': 'WrongPassword!',
        'remember_me': False,
    }, follow_redirects=True)

    assert response.status_code == 200


@patch('app.auth.routes.send_validate_email')
def test_password_reset_workflow(mock_send_email, client, app) -> None:
    """Test requesting a password reset and using the token to change it."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'resetuser_{unique_suffix}'
    test_email = f'{test_username}@expenseapp.ch'

    with app.app_context():
        user = User(username=test_username, email=test_email, locale='en')
        user.set_password('OldPassword123')
        user.get_token()
        db.session.add(user)
        db.session.commit()

    reset_request_response = client.post('/auth/reset_authentication', data={
        'email': test_email,
    }, follow_redirects=True)

    assert reset_request_response.status_code == 200
    assert mock_send_email.called

    with app.app_context():
        user = User.query.filter_by(username=test_username).first()
        token = user.get_reset_password_token()

    reset_response = client.post(f'/auth/register_password/{token}', data={
        'password': 'NewPassword123!',
        'password2': 'NewPassword123!',
        'confirm_password': 'NewPassword123!',
    }, follow_redirects=True)

    assert reset_response.status_code == 200

    with app.app_context():
        updated_user = User.query.filter_by(username=test_username).first()
        assert updated_user.check_password('NewPassword123!') is True
        assert updated_user.check_password('OldPassword123') is False
