# coding=utf-8
"""Tests for model-level fixes: gravatar fallbacks and File read-error tracking."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from flask import Flask

from app import db
from app.models import MISSING_IMAGE_DATA_URI, EventUser, File, User


# ---------------------------------------------------------------------------
# gravatar() fallback when no email is set
# ---------------------------------------------------------------------------

def test_user_gravatar_without_email(app: Flask) -> None:
    """User.gravatar falls back to the GUID when the email is missing."""
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        user = User(username=f'grav_{suffix}', email=f'grav_{suffix}@example.com', locale='en')
        db.session.add(user)
        db.session.commit()

        user.email = None
        url = user.gravatar(128)

        assert url.startswith('https://www.gravatar.com/avatar/')
        assert 's=128' in url


def test_eventuser_gravatar_without_email_is_stable(app: Flask) -> None:
    """EventUser.gravatar is deterministic when no email is set."""
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        eu = EventUser(
            username=f'eu_{suffix}', email=None, weighting=1.0, locale='en',
        )
        db.session.add(eu)
        db.session.commit()

        first = eu.gravatar(64)
        second = eu.gravatar(64)

        assert first == second
        assert first.startswith('https://www.gravatar.com/avatar/')


def test_eventuser_gravatar_without_email_is_unique(app: Flask) -> None:
    """Two email-less participants get different identicons."""
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        first = EventUser(username=f'a_{suffix}', email=None, weighting=1.0, locale='en')
        second = EventUser(username=f'b_{suffix}', email=None, weighting=1.0, locale='en')
        db.session.add_all([first, second])
        db.session.commit()

        assert first.gravatar(64) != second.gravatar(64)


def test_eventuser_avatar_without_email_does_not_raise(app: Flask) -> None:
    """EventUser.avatar works for participants without an email address."""
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        eu = EventUser(username=f'av_{suffix}', email=None, weighting=1.0, locale='en')
        db.session.add(eu)
        db.session.commit()

        assert eu.avatar(128).startswith('https://www.gravatar.com/avatar/')


# ---------------------------------------------------------------------------
# File.read_error tracking
# ---------------------------------------------------------------------------

def _make_file(storage_key: str) -> File:
    """Create and persist a File row pointing at *storage_key*."""
    file_obj = File(
        original_filename='broken.png',
        storage_backend='local',
        storage_key=storage_key,
        mime_type='image/png',
        file_size=1,
    )
    db.session.add(file_obj)
    db.session.commit()
    return file_obj


def test_mark_read_error_sets_flag_and_logs_error_once(app: Flask) -> None:
    """First failure logs ERROR and sets the flag; the second logs WARNING."""
    with app.app_context():
        file_obj = _make_file(f'missing/{uuid.uuid4().hex}.png')
        assert not file_obj.read_error

        with patch.object(app.logger, 'error') as err, patch.object(app.logger, 'warning') as warn:
            file_obj.mark_read_error(FileNotFoundError('no such file'))
            assert err.call_count == 1
            assert warn.call_count == 0

        assert file_obj.read_error is True

        # Second failure must not raise another ERROR (no duplicate alert email)
        with patch.object(app.logger, 'error') as err, patch.object(app.logger, 'warning') as warn:
            file_obj.mark_read_error(FileNotFoundError('no such file'))
            assert err.call_count == 0
            assert warn.call_count == 1


def test_clear_read_error_resets_flag(app: Flask) -> None:
    """A previously flagged file is un-flagged once it becomes readable."""
    with app.app_context():
        file_obj = _make_file(f'missing/{uuid.uuid4().hex}.png')
        file_obj.mark_read_error(FileNotFoundError('gone'))
        assert file_obj.read_error is True

        file_obj.clear_read_error()

        assert file_obj.read_error is False


def test_clear_read_error_is_noop_when_not_flagged(app: Flask) -> None:
    """clear_read_error does nothing when the file was never flagged."""
    with app.app_context():
        file_obj = _make_file(f'ok/{uuid.uuid4().hex}.png')

        with patch.object(app.logger, 'info') as info:
            file_obj.clear_read_error()
            assert info.call_count == 0

        assert not file_obj.read_error


def test_get_data_uri_returns_marker_when_unreadable(app: Flask) -> None:
    """get_data_uri returns a visible placeholder instead of raising."""
    with app.app_context():
        file_obj = _make_file(f'missing/{uuid.uuid4().hex}.png')

        result = file_obj.get_data_uri()

        assert result == MISSING_IMAGE_DATA_URI
        assert result.startswith('data:image/svg+xml;base64,')
        assert file_obj.read_error is True


def test_file_class_stats_reports_read_errors(app: Flask) -> None:
    """File.get_class_stats includes a read-error entry when files are flagged."""
    with app.app_context():
        file_obj = _make_file(f'missing/{uuid.uuid4().hex}.png')
        file_obj.mark_read_error(FileNotFoundError('gone'))

        labels = [str(label) for label, _count in File.get_class_stats()]

        assert any('read error' in label.lower() for label in labels)


# ---------------------------------------------------------------------------
# media_service integration — the path that used to email on every request
# ---------------------------------------------------------------------------

def test_get_file_bytes_flags_and_only_alerts_once(app: Flask) -> None:
    """Serving an unreadable file returns None and alerts only on first failure."""
    from app.services.media_service import get_file_bytes

    with app.app_context():
        file_obj = _make_file(f'missing/{uuid.uuid4().hex}.png')
        file_id = file_obj.id

        with patch.object(app.logger, 'error') as err:
            assert get_file_bytes(file_id) is None
            assert err.call_count == 1

        assert db.session.get(File, file_id).read_error is True

        # Repeated requests must not produce further ERROR logs (no email flood)
        with patch.object(app.logger, 'error') as err:
            assert get_file_bytes(file_id) is None
            assert get_file_bytes(file_id) is None
            assert err.call_count == 0
