# -*- coding: utf-8 -*-
"""Concurrency stress test for simultaneous profile edits."""

from __future__ import annotations

import concurrent.futures

import pytest

from app import db
from app.models import User


@pytest.mark.parametrize('app', ['local'], indirect=True)
def test_concurrent_profile_edits(app) -> None:
    """Test 20 clients trying to edit profiles at the exact same millisecond."""
    # Setup: create 20 dummy users sequentially before the chaos starts
    with app.app_context():
        for i in range(20):
            user = User(username=f'threaduser_{i}', email=f'threaduser_{i}@expenseapp.ch', locale='en')
            user.set_password('TestPass123')
            user.get_token()
            db.session.add(user)
        db.session.commit()

    def concurrent_worker(thread_id: int) -> int:
        """Simulate a single user logging in and making a request."""
        client = app.test_client()
        username = f'threaduser_{thread_id}'

        client.post('/auth/authenticate_password', data={
            'username': username,
            'password': 'TestPass123',
            'remember_me': False,
        }, follow_redirects=True)

        response = client.post('/edit_profile', data={
            'username': username,
            'about_me': f'I was updated by concurrent thread {thread_id}!',
            'locale': 'en',
        }, follow_redirects=True)

        return response.status_code

    # Fire 20 threads simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(concurrent_worker, range(20)))

    assert all(status == 200 for status in results), "One or more concurrent requests failed!"

    # Verify the database handled the concurrent locks and saved everything
    with app.app_context():
        users = User.query.filter(User.username.like('threaduser_%')).all()
        assert len(users) == 20
        for user in users:
            assert "I was updated by concurrent thread" in user.about_me
