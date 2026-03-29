# coding=utf-8
"""Tests for main blueprint routes: dashboard, profile, messaging."""
from __future__ import annotations

import uuid

from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import Message, User


def test_index_and_explore(auth_client: FlaskClient) -> None:
    """Test the primary dashboard and explore feeds."""
    response = auth_client.get('/index', follow_redirects=True)
    assert response.status_code == 200


def test_user_profile_page(auth_client: FlaskClient, app: Flask) -> None:
    """Test viewing a specific user's profile."""
    with app.app_context():
        testuser = User.query.filter_by(username='testuser').first()
        testuser_guid = testuser.guid

    response = auth_client.get(f'/user/{testuser_guid}')
    assert response.status_code == 200
    assert b"testuser" in response.data


def test_edit_profile(auth_client: FlaskClient, app: Flask) -> None:
    """Test that a user can successfully update their settings."""
    response = auth_client.post('/edit_profile', data={
        'username': 'testuser',
        'about_me': 'This is my brand new bio updated by Pytest!',
        'locale': 'en'
    }, follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        assert user.about_me == 'This is my brand new bio updated by Pytest!'


def test_messaging_system(auth_client: FlaskClient, app: Flask) -> None:
    """Test sending and reading private messages."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'receiver_{unique_suffix}'

    with app.app_context():
        recipient = User(username=test_username, email=f'{test_username}@expenseapp.ch', locale='en')
        recipient.set_password('TestPass123')
        recipient.get_token()
        db.session.add(recipient)
        db.session.commit()
        recipient_id = recipient.id

    send_resp = auth_client.post('/messages', data={
        'recipient_id': recipient_id,
        'message': f'{unique_suffix} | Hello from the Pytest suite!'
    }, follow_redirects=True)
    assert send_resp.status_code == 200

    with app.app_context():
        msg = Message.query.filter_by(body=f'{unique_suffix} | Hello from the Pytest suite!').first()
        assert msg is not None
        assert msg.author.username == 'testuser'
        assert msg.recipient.username == test_username

    inbox_resp = auth_client.get('/messages')
    assert inbox_resp.status_code == 200