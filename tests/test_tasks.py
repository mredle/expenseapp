# coding=utf-8
"""Tests for RQ background tasks: error handling, exports, log cleanup, rate updates."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

from flask import Flask
from PIL import Image as ImagePIL

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import Currency, Event, EventUser, Log, Post, Task, User
from app.tasks import (
    _clean_session,
    _set_task_progress,
    clean_log,
    consume_time,
    export_posts,
    get_balance_pdf,
    type_error,
    update_rates_yahoo,
)


def test_task_type_error(app: Flask) -> None:
    """Test that the type_error task catches its own exception and doesn't crash the worker."""
    user = User.query.first()
    type_error(user.guid)


@patch('app.tasks.time.sleep')
@patch('app.tasks.send_email')
def test_task_consume_time(mock_send_email: MagicMock, mock_sleep: MagicMock, app: Flask) -> None:
    """Test that consume_time sleeps and then sends an email."""
    user = User.query.first()
    consume_time(user.guid, 2)

    assert mock_sleep.call_count == 2
    assert mock_send_email.called


@patch('app.tasks.send_email')
def test_task_export_posts(mock_send_email: MagicMock, app: Flask) -> None:
    """Test that export_posts generates a posts.json attachment and emails it."""
    user = User.query.first()

    event = Event(
        name='Task Event',
        date=datetime.now(timezone.utc),
        admin=user,
        base_currency=Currency.query.first(),
        currencies=[Currency.query.first()],
        exchange_fee=0,
        fileshare_link=''
    )
    eventuser = EventUser(username=user.username, email=user.email, weighting=1.0, locale='en')
    eventuser.event = event

    post = Post(body='Task test post', timestamp=datetime.now(timezone.utc), author=eventuser, event=event)

    db.session.add_all([event, eventuser, post])
    db.session.commit()

    export_posts(user.guid)
    assert mock_send_email.called
    _args, kwargs = mock_send_email.call_args

    assert 'posts.json' in kwargs['attachments'][0][0]


def test_task_clean_log(app: Flask) -> None:
    """Test that the housekeeping function deletes old logs."""
    old_date = datetime.now(timezone.utc) - timedelta(days=400)
    user = User.query.first()
    log = Log(severity='INFORMATION', module='test', msg_type='test', msg='very old log', user=user)
    log.date = old_date
    db.session.add(log)
    db.session.commit()

    clean_log(False, 360)

    deleted_log = Log.query.filter_by(msg='very old log').first()
    assert deleted_log is None


@patch('app.tasks.YahooFinancials')
def test_task_update_rates_yahoo(mock_yahoo: MagicMock, app: Flask) -> None:
    """Test that the Yahoo currency updater processes data correctly without making real API calls."""
    user = User.query.first()

    mock_instance = MagicMock()
    mock_yahoo.return_value = mock_instance
    mock_instance.get_historical_price_data.return_value = {
        'CHF=X': {'currency': 'USD', 'prices': [{'adjclose': 1.1}]},
        'EUR=X': {'currency': 'EUR', 'prices': [{'adjclose': 0.95}]}
    }

    if not Currency.query.filter_by(code='EUR').first():
        db.session.add(Currency(name='Euro', code='EUR', number=978, exponent=2, inCHF=1.0))
        db.session.commit()

    update_rates_yahoo(user.guid)

    assert mock_instance.get_historical_price_data.called
    logs = Log.query.filter_by(msg_type='get_rates_yahoo').all()
    assert len(logs) > 0


def test_get_balance_pdf_with_event_image(app: Flask) -> None:
    """get_balance_pdf must not raise when the event has an image and no request context.

    Reproduces: RuntimeError: Unable to build URLs outside an active request without
    'SERVER_NAME' configured — raised when url_for() was called from within an RQ
    worker (app context only, no request context) while rendering the balance PDF
    template for an event that had an image attached.

    The fix embeds images as base64 data URIs (avatar_data_uri) so url_for() is
    never called from within the PDF rendering path.
    """
    from app.media.processor import process_and_store_image

    user = User.query.first()
    currency = Currency.query.first()

    # Create a minimal event with admin + accountant
    event = Event(
        name='PDF Image Test Event',
        date=datetime.now(timezone.utc),
        admin=user,
        base_currency=currency,
        currencies=[currency],
        exchange_fee=0.0,
        fileshare_link='',
    )
    db.session.add(event)
    db.session.flush()

    eu = EventUser(
        username=user.username,
        email=user.email,
        weighting=1.0,
        locale='en',
        user_id=user.id,
    )
    eu.event_id = event.id
    db.session.add(eu)
    db.session.flush()
    event.accountant = eu

    # Attach a minimal JPEG image so the {% if event.image %} branch is entered.
    # Use a UUID-derived unique colour so the hash-based deduplication in
    # process_and_store_image never matches a file created by the sibling
    # parameterised variant ('local' vs 's3'), which would return a stale File
    # record pointing at an already-deleted temp directory.
    uid = uuid.uuid4().hex
    r, g, b = int(uid[:2], 16), int(uid[2:4], 16), int(uid[4:6], 16)
    img = ImagePIL.new('RGB', (16, 16), color=(r, g, b))
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    image_obj = process_and_store_image(img_io, 'event_test.jpg')
    event.image = image_obj

    db.session.commit()

    # Verify we are NOT inside a request context (mirroring the RQ worker environment)
    from flask import has_request_context
    assert not has_request_context(), 'Test must run without a request context to be meaningful'

    # Before the fix this raised:
    #   RuntimeError: Unable to build URLs outside an active request without 'SERVER_NAME'
    result = get_balance_pdf(event, 'en', recalculate=False)

    assert isinstance(result, bytes), 'get_balance_pdf must return bytes'
    assert result[:4] == b'%PDF', 'Returned bytes must be a PDF document'


@patch('app.tasks.get_current_job')
def test_set_task_progress_non_fatal_on_db_error(mock_get_job: MagicMock, app: Flask) -> None:
    """_set_task_progress must not raise when the DB commit fails.

    Reproduces the secondary failure mode where a SQLAlchemyError inside
    _set_task_progress (e.g. MariaDB 1020 on add_notification) would kill
    the whole job.  After the fix the error is caught, the session is rolled
    back, and the function returns without propagating the exception.
    """
    fake_job = MagicMock()
    fake_job.id = 'fake-job-id'
    fake_job.meta = {}
    mock_get_job.return_value = fake_job

    with app.app_context():
        # Simulate a DB commit failure during notification write
        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('simulated')):
            # Must not raise — _set_task_progress is best-effort
            _set_task_progress(50)

        # Session must be usable after the rollback (no PendingRollbackError)
        _ = db.session.execute(db.select(Task).limit(1)).scalars().all()


def test_clean_session_decorator_resets_session(app: Flask) -> None:
    """_clean_session must call db.session.remove() before and after the wrapped function.

    Verifies that the decorator always removes the session both before the job
    starts (clearing stale identity-map state) and in the finally block
    (returning the connection to the pool), even when the wrapped function
    raises an exception.
    """
    remove_calls: list[str] = []

    with patch.object(db.session, 'remove', side_effect=lambda: remove_calls.append('remove')):
        # Normal path — wrapped function succeeds
        @_clean_session
        def succeeding_task(x: int) -> int:
            return x * 2

        result = succeeding_task(21)
        assert result == 42
        assert remove_calls.count('remove') == 2, 'remove() must be called before and after'

        remove_calls.clear()

        # Error path — wrapped function raises; remove() must still be called in finally
        @_clean_session
        def failing_task() -> None:
            raise RuntimeError('boom')

        try:
            failing_task()
        except RuntimeError:
            pass
        assert remove_calls.count('remove') == 2, 'remove() must be called even when task raises'