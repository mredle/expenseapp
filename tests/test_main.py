# -*- coding: utf-8 -*-
import pytest
import uuid
from app import db
from app.models import User, Post, Message

def test_index_and_explore(auth_client):
    """Test the primary dashboard and explore feeds."""
    # 1. Test the main dashboard
    response = auth_client.get('/index', follow_redirects=True)
    assert response.status_code == 200


def test_user_profile_page(auth_client, app):
    """Test viewing a specific user's profile."""
    # First, get testuser's GUID!
    with app.app_context():
        testuser = User.query.filter_by(username='testuser').first()
        testuser_guid = testuser.guid
        
    # Then query the profile using the GUID!
    response = auth_client.get(f'/user/{testuser_guid}')
    assert response.status_code == 200
    assert b"testuser" in response.data


def test_edit_profile(auth_client, app):
    """Test that a user can successfully update their settings."""
    # 1. Post new data to the edit profile route
    response = auth_client.post('/edit_profile', data={
        'username': 'testuser', # Keeping the same username
        'about_me': 'This is my brand new bio updated by Pytest!',
        'locale': 'en'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # 2. Verify the database actually saved the new bio
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        assert user.about_me == 'This is my brand new bio updated by Pytest!'


def test_messaging_system(auth_client, app):
    """Test sending and reading private messages."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f'receiver_{unique_suffix}'

    # 1. Setup: Create a recipient
    with app.app_context():
        recipient = User(username=test_username, email=f'{test_username}@expenseapp.ch', locale='en')
        recipient.set_password('TestPass123')
        recipient.get_token()

        db.session.add(recipient)
        db.session.commit()
        recipient_id = recipient.id
    
    # 2. Send a message
    send_resp = auth_client.post('/messages', data={
        'recipient_id': recipient_id, 
        'message': f'{unique_suffix} | Hello from the Pytest suite!'
    }, follow_redirects=True)
    assert send_resp.status_code == 200
    
    # 3. Verify it shows up in the database attached to the right people
    with app.app_context():
        msg = Message.query.filter_by(body=f'{unique_suffix} | Hello from the Pytest suite!').first()
        assert msg is not None
        assert msg.author.username == 'testuser'
        assert msg.recipient.username == test_username
        
    # 4. View the messages inbox
    inbox_resp = auth_client.get('/messages')
    assert inbox_resp.status_code == 200