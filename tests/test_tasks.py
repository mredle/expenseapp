# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from app import db
from app.models import User, Post, Log, Currency, Event, EventUser
from app.tasks import type_error, consume_time, export_posts, clean_log, update_rates_yahoo

def test_task_type_error(app):
    """Test that the type_error task catches its own exception and doesn't crash the worker."""
    user = User.query.first()
    type_error(user.guid) # Will internally trigger an exception, but safely catch it

@patch('app.tasks.time.sleep') # Mocks time.sleep so the test runs instantly!
@patch('app.tasks.send_email') # Intercepts the email
def test_task_consume_time(mock_send_email, mock_sleep, app):
    """Test that consume_time sleeps and then sends an email."""
    user = User.query.first()
    consume_time(user.guid, 2) # Ask it to sleep for 2 seconds
    
    assert mock_sleep.call_count == 2
    assert mock_send_email.called

@patch('app.tasks.send_email')
def test_task_export_posts(mock_send_email, app):
    user = User.query.first()
    
    # Create a dummy Event and EventUser so we can legally create a Post
    event = Event(name='Task Event', date=datetime.now(timezone.utc), admin=user, base_currency=Currency.query.first(), currencies=[Currency.query.first()], exchange_fee=0, fileshare_link='')
    eventuser = EventUser(username=user.username, email=user.email, weighting=1.0, locale='en')
    eventuser.event = event
    
    post = Post(body='Task test post', timestamp=datetime.now(timezone.utc), author=eventuser, event=event)
    
    db.session.add_all([event, eventuser, post])
    db.session.commit()
    
    export_posts(user.guid)
    assert mock_send_email.called
    args, kwargs = mock_send_email.call_args

    # Verify the attachment is named posts.json
    assert 'posts.json' in kwargs['attachments'][0][0] 

def test_task_clean_log(app):
    """Test that the housekeeping function deletes old logs."""
    # Create a dummy log entry 400 days old
    old_date = datetime.now(timezone.utc) - timedelta(days=400)
    user = User.query.first()
    log = Log(severity='INFORMATION', module='test', msg_type='test', msg='very old log', user=user)
    log.date = old_date
    db.session.add(log)
    db.session.commit()
    
    clean_log(False, 360) 
    
    # FIX: Change filter_by(message=...) to filter_by(msg=...)
    deleted_log = Log.query.filter_by(msg='very old log').first()
    assert deleted_log is None

@patch('app.tasks.YahooFinancials')
def test_task_update_rates_yahoo(mock_yahoo, app):
    """Test that the Yahoo currency updater processes data correctly without making real API calls."""
    user = User.query.first()
    
    # 1. Create a Fake Yahoo Finance API Response
    mock_instance = MagicMock()
    mock_yahoo.return_value = mock_instance
    mock_instance.get_historical_price_data.return_value = {
        'CHF=X': {'currency': 'USD', 'prices': [{'adjclose': 1.1}]}, # Base currency
        'EUR=X': {'currency': 'EUR', 'prices': [{'adjclose': 0.95}]} # Target currency
    }
    
    # 2. Add EUR to the DB so the loop has something to process
    if not Currency.query.filter_by(code='EUR').first():
        db.session.add(Currency(name='Euro', code='EUR', number=978, exponent=2, inCHF=1.0))
        db.session.commit()
        
    # 3. Trigger the task
    update_rates_yahoo(user.guid)
    
    # 4. Verify Yahoo was called and success logs were generated
    assert mock_instance.get_historical_price_data.called
    logs = Log.query.filter_by(msg_type='get_rates_yahoo').all()
    assert len(logs) > 0