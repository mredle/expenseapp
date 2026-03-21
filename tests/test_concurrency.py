# -*- coding: utf-8 -*-
import pytest
import uuid
import concurrent.futures
from app import db
from app.models import User

# Skip this test for SQLite, or it will throw "database is locked" errors!
# SQLite cannot handle high-concurrency writes.
@pytest.mark.parametrize('app', ['local'], indirect=True)
def test_concurrent_profile_edits(app):
    """Test 20 clients trying to edit profiles at the exact same millisecond."""
    
    # 1. SETUP: Create 20 dummy users sequentially before the chaos starts
    with app.app_context():
        for i in range(20):
            user = User(username=f'threaduser_{i}', email=f'threaduser_{i}@expenseapp.ch', locale='en')
            user.set_password('TestPass123')
            user.get_token()
            db.session.add(user)
        db.session.commit()

    # 2. THE WORKER: This is the function each concurrent client will run
    def concurrent_worker(thread_id):
        """Simulate a single user logging in and making a request."""
        # CRITICAL: Every thread MUST instantiate its own fresh test client!
        client = app.test_client()
        username = f'threaduser_{thread_id}'
        
        # Log this specific thread's client in
        client.post('/auth/authenticate_password', data={
            'username': username,
            'password': 'TestPass123',
            'remember_me': False
        }, follow_redirects=True)
        
        # Blast the server with an edit request
        response = client.post('/edit_profile', data={
            'username': username,
            'about_me': f'I was updated by concurrent thread {thread_id}!',
            'locale': 'en'
        }, follow_redirects=True)
        
        return response.status_code

    # 3. THE BLAST: Fire 20 threads simultaneously
    # ThreadPoolExecutor spins up multiple operating system threads to hit your app at once
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # Map the worker function to thread IDs 0 through 19
        results = list(executor.map(concurrent_worker, range(20)))

    # 4. VERIFY: Ensure all 20 threads received a 200 OK
    assert all(status == 200 for status in results), "One or more concurrent requests failed!"

    # 5. VERIFY DB: Ensure the database handled the concurrent locks and saved everything
    with app.app_context():
        users = User.query.filter(User.username.like('threaduser_%')).all()
        assert len(users) == 20
        for user in users:
            assert "I was updated by concurrent thread" in user.about_me