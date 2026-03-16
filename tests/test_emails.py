# -*- coding: utf-8 -*-
from unittest.mock import patch
from app.models import User
from app.auth.email import send_newuser_notification

@patch('app.auth.email.send_email') 
def test_send_newuser_notification(mock_send_email, app):
    """Test that the new user email formatting works."""
    with app.app_context():
        user = User(username='emailtest', email='emailtest@expenseapp.local', locale='en')
        
        send_newuser_notification(user)
        assert mock_send_email.called
        args, kwargs = mock_send_email.call_args
        
        # FIX: Check args[0] because subject is a positional argument!
        assert "New user has registered on ExpenseApp!" in args[0]
