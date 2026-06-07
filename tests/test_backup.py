# coding=utf-8
"""Tests for backup service: create, execute, list, export, import, restore, and delete."""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models import BackupSet, Currency, Event, EventUser, User
from app.services import backup_service
from app.tasks import run_backup, run_restore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin(app: Flask) -> User:
    """Return (creating if needed) an admin user for backup operations."""
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        if not user:
            user = User(username='backupadmin', email='backupadmin@test.ch', locale='en')
            user.set_password('pw')
            user.is_admin = True
            db.session.add(user)
            db.session.commit()
        return user


def _make_currency(app: Flask) -> Currency:
    """Return (creating if needed) a CHF test currency."""
    with app.app_context():
        c = Currency.query.filter_by(code='CHF').first()
        if not c:
            c = Currency(
                code='CHF', name='Swiss Franc', number=756, exponent=2, inCHF=1.0,
                description='Test',
            )
            db.session.add(c)
            db.session.commit()
        return c


# ---------------------------------------------------------------------------
# create_backup
# ---------------------------------------------------------------------------

def test_create_backup_full(app: Flask) -> None:
    """create_backup returns a BackupSet with pending segments for a full backup."""
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        result = backup_service.create_backup(
            name='Test full backup',
            segment_types=['currencies', 'users', 'logs', 'system'],
            user=user,
        )
        assert result.success
        assert result.backup_set is not None
        bs = result.backup_set
        assert bs.status in ('pending', 'running', 'completed', 'failed')
        assert bs.total_segments == 4


def test_create_backup_partial_event(app: Flask) -> None:
    """create_backup with event_guids creates one event segment per GUID."""
    _make_admin(app)
    _make_currency(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        currency = Currency.query.filter_by(code='CHF').first()
        event = Event(
            name='Partial event', date=datetime.now(timezone.utc),
            admin=user, base_currency=currency, currencies=[currency],
            exchange_fee=0.0, fileshare_link='', closed=False, description='',
        )
        db.session.add(event)
        db.session.commit()
        event_guid = str(event.guid)

        result = backup_service.create_backup(
            name='Partial backup',
            segment_types=['events'],
            user=user,
            event_guids=[event_guid],
        )
        assert result.success
        assert result.backup_set.total_segments == 1
        seg = result.backup_set.segments[0]
        assert seg.segment_type == 'event'
        assert seg.segment_key == event_guid


# ---------------------------------------------------------------------------
# execute_backup_segment
# ---------------------------------------------------------------------------

def test_execute_currencies_segment(app: Flask) -> None:
    """execute_backup_segment for currencies completes with size > 0."""
    _make_admin(app)
    _make_currency(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        result = backup_service.create_backup(
            name='Currency segment test',
            segment_types=['currencies'],
            user=user,
        )
        assert result.success
        seg = result.backup_set.segments[0]
        backup_service.execute_backup_segment(seg)
        assert seg.status == 'completed'
        assert seg.file_size > 0
        assert seg.checksum is not None
        assert seg.record_count >= 1  # CHF created above


def test_execute_users_segment(app: Flask) -> None:
    """execute_backup_segment for users completes successfully."""
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        result = backup_service.create_backup(
            name='Users segment test', segment_types=['users'], user=user,
        )
        assert result.success
        seg = result.backup_set.segments[0]
        backup_service.execute_backup_segment(seg)
        assert seg.status == 'completed'
        assert seg.record_count >= 1


def test_execute_event_segment(app: Flask) -> None:
    """execute_backup_segment for an event segment completes with record_count == 1."""
    _make_admin(app)
    _make_currency(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        currency = Currency.query.filter_by(code='CHF').first()
        event = Event(
            name='Event seg test', date=datetime.now(timezone.utc),
            admin=user, base_currency=currency, currencies=[currency],
            exchange_fee=0.0, fileshare_link='', closed=False, description='',
        )
        db.session.add(event)
        db.session.commit()
        event_guid = str(event.guid)

        result = backup_service.create_backup(
            name='Event seg backup', segment_types=['events'],
            user=user, event_guids=[event_guid],
        )
        assert result.success
        seg = result.backup_set.segments[0]
        backup_service.execute_backup_segment(seg)
        assert seg.status == 'completed'
        assert seg.record_count == 1


# ---------------------------------------------------------------------------
# list_backups / get_backup / delete_backup
# ---------------------------------------------------------------------------

def test_list_backups(app: Flask) -> None:
    """list_backups returns a PaginatedResult with the created backup set."""
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        backup_service.create_backup(name='List test', segment_types=['logs'], user=user)
        result = backup_service.list_backups(1)
        assert result.total >= 1
        assert len(result.items) >= 1


def test_get_backup_found(app: Flask) -> None:
    """get_backup returns the BackupSet for a known GUID."""
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        cr = backup_service.create_backup(name='Get test', segment_types=['logs'], user=user)
        guid = str(cr.backup_set.guid)
        bs = backup_service.get_backup(guid)
        assert bs is not None
        assert str(bs.guid) == guid


def test_get_backup_not_found(app: Flask) -> None:
    """get_backup returns None for an unknown GUID."""
    with app.app_context():
        bs = backup_service.get_backup(uuid.uuid4().hex)
        assert bs is None


def test_delete_backup(app: Flask) -> None:
    """delete_backup removes the BackupSet from the database."""
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        cr = backup_service.create_backup(name='Delete test', segment_types=['logs'], user=user)
        guid = str(cr.backup_set.guid)
        result = backup_service.delete_backup(guid)
        assert result.success
        assert backup_service.get_backup(guid) is None


# ---------------------------------------------------------------------------
# export / import roundtrip
# ---------------------------------------------------------------------------

def test_export_import_roundtrip(app: Flask) -> None:
    """A backup set can be exported as .tar.gz and re-imported successfully."""
    _make_admin(app)
    _make_currency(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        cr = backup_service.create_backup(
            name='Export roundtrip', segment_types=['currencies'], user=user,
        )
        assert cr.success
        bs = cr.backup_set
        for seg in bs.segments:
            backup_service.execute_backup_segment(seg)
        bs.status = 'completed'
        bs.completed_segments = bs.segments.count()
        db.session.commit()

        # Export
        export_result = backup_service.export_backup(str(bs.guid))
        assert export_result.success
        assert export_result.archive_bytes is not None
        assert export_result.filename.endswith('.tar.gz')

        # Import
        import_result = backup_service.import_backup(
            io.BytesIO(export_result.archive_bytes), user,
        )
        assert import_result.success
        assert import_result.backup_set is not None
        assert 'Imported:' in import_result.backup_set.name


# ---------------------------------------------------------------------------
# enforce_retention
# ---------------------------------------------------------------------------

def test_enforce_retention(app: Flask) -> None:
    """enforce_retention deletes the oldest completed backups beyond the limit."""
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        for i in range(5):
            cr = backup_service.create_backup(
                name=f'Retention test {i}', segment_types=['logs'], user=user,
            )
            assert cr.success
            cr.backup_set.status = 'completed'
            db.session.commit()

        # The function tries to delete storage files; on S3 test env those may not
        # exist but the DB records should still be pruned to max_count.
        backup_service.enforce_retention(max_count=3)

        remaining = BackupSet.query.filter(BackupSet.status == 'completed').count()
        assert remaining <= 3


# ---------------------------------------------------------------------------
# GUI routes (admin only)
# ---------------------------------------------------------------------------

def test_backups_page_requires_admin(app: Flask, auth_client: FlaskClient) -> None:
    """Non-admin users are redirected when accessing the backups page."""
    resp = auth_client.get('/backups', follow_redirects=True)
    assert resp.status_code == 200
    # Should be redirected away, not show backup management UI
    assert b'Only an admin' in resp.data or b'backups' not in resp.data.lower()


def test_backups_page_admin(app: Flask, admin_client: FlaskClient) -> None:
    """Admin can access the backups page successfully."""
    resp = admin_client.get('/backups')
    assert resp.status_code == 200
    assert b'backup' in resp.data.lower()


def test_create_backup_post(app: Flask, admin_client: FlaskClient) -> None:
    """Admin can POST to create a backup; redirects to /backups."""
    resp = admin_client.post(
        '/backups/create',
        data={'name': 'GUI test backup'},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 200)


def test_delete_backup_gui(app: Flask, admin_client: FlaskClient) -> None:
    """Admin can delete a backup via the GUI route."""
    with app.app_context():
        admin = User.query.filter_by(username='testadmin').first()
        cr = backup_service.create_backup(name='GUI del test', segment_types=['logs'], user=admin)
        guid = str(cr.backup_set.guid)

    resp = admin_client.post(f'/backups/{guid}/delete', follow_redirects=False)
    assert resp.status_code in (302, 200)


# ---------------------------------------------------------------------------
# RQ task signature regression tests
# ---------------------------------------------------------------------------

def test_run_backup_task_via_worker_convention(app: Flask) -> None:
    """run_backup accepts (guid, backup_set_guid=...) matching the launch_task convention.

    This exercises the actual calling signature that RQ uses: launch_task injects
    the user GUID as the first positional arg; backup_set_guid arrives as a kwarg.
    A TypeError here means the leading guid param is missing.
    """
    _make_admin(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        cr = backup_service.create_backup(
            name='Task sig test backup',
            segment_types=['logs'],
            user=user,
        )
        assert cr.success
        bs_guid = str(cr.backup_set.guid)
        user_guid = str(user.guid)

    with app.app_context():
        run_backup(user_guid, backup_set_guid=bs_guid)
        bs = BackupSet.query.filter(BackupSet.guid == bs_guid).first()
        assert bs is not None
        assert bs.status in ('completed', 'failed')


def test_run_restore_task_via_worker_convention(app: Flask) -> None:
    """run_restore accepts (guid, backup_set_guid=..., strategy=...) matching launch_task.

    Mirrors test_run_backup_task_via_worker_convention for the restore path.
    A TypeError here means the leading guid param is missing from run_restore.
    """
    _make_admin(app)
    _make_currency(app)
    with app.app_context():
        user = User.query.filter_by(username='backupadmin').first()
        cr = backup_service.create_backup(
            name='Task sig test restore',
            segment_types=['currencies'],
            user=user,
        )
        assert cr.success
        bs = cr.backup_set
        for seg in bs.segments:
            backup_service.execute_backup_segment(seg)
        bs.status = 'completed'
        bs.completed_segments = bs.segments.count()
        db.session.commit()
        bs_guid = str(bs.guid)
        user_guid = str(user.guid)

    with app.app_context():
        # Must not raise TypeError — that would mean the leading guid param is absent
        run_restore(user_guid, backup_set_guid=bs_guid, strategy='skip')


def test_restore_users_reconciles_by_email_not_just_guid(app: Flask) -> None:
    """restore_users must not raise IntegrityError when the target DB already has a user
    with the same email/username but a different GUID (e.g. after flask dbinit re-seeds).

    Reproduces:
      sqlalchemy.exc.IntegrityError: (1062, "Duplicate entry 'anonymous@mystery.ch'
      for key 'ix_users_email'")

    Pre-fix, the users segment was rolled back entirely because restore_users matched
    only on GUID.  The fix adds OR email OR username to the lookup, so colliding rows
    are treated as already-present and skipped/updated rather than re-inserted.
    """
    _make_admin(app)
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = User.query.filter_by(username='backupadmin').first()

        # Create a user that will be present in the backup
        collider = User(
            username=f'collider_{suffix}',
            email=f'collider_{suffix}@test.ch',
            locale='en',
        )
        collider.set_password('pw')
        db.session.add(collider)
        db.session.commit()

        # Back up the users segment while the user has its original GUID
        cr = backup_service.create_backup(
            name=f'User email collision test {suffix}',
            segment_types=['users'],
            user=admin,
        )
        assert cr.success
        bs = cr.backup_set
        for seg in bs.segments:
            backup_service.execute_backup_segment(seg)
        bs.status = 'completed'
        bs.completed_segments = bs.segments.count()
        db.session.commit()
        bs_guid = str(bs.guid)

        # Simulate a re-seeded DB: replace the collider's GUID with a fresh one,
        # keeping email + username the same (identical to the dbinit anonymous-user scenario).
        collider_fresh = User.query.filter_by(username=f'collider_{suffix}').first()
        collider_fresh.guid = uuid.uuid4()
        db.session.commit()

        # Restore — must NOT raise IntegrityError and must NOT create a duplicate
        totals = backup_service.apply_restore(bs, 'skip')

        users_key = next(k for k in totals if k.startswith('users:'))
        assert 'error' not in totals[users_key], (
            f'restore_users raised an error: {totals[users_key].get("error")}'
        )
        count = User.query.filter_by(email=f'collider_{suffix}@test.ch').count()
        assert count == 1, f'Expected 1 row for collider email, got {count} (duplicate inserted)'


def test_restore_currencies_reconciles_by_code_not_just_guid(app: Flask) -> None:
    """restore_currencies must not insert duplicates when the target DB already has a
    currency with the same code but a different GUID (e.g. after flask dbinit re-seeds).

    Pre-fix, restore_currencies matched only on GUID, so re-seeded currencies (same code,
    new GUID) were silently inserted as duplicates — correct counts were reported but the
    table had doubled rows.  The fix adds OR Currency.code to the lookup.
    """
    _make_admin(app)
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = User.query.filter_by(username='backupadmin').first()

        # Create a currency that will be in the backup
        code = f'T{suffix[:2].upper()}'
        c = Currency(code=code, name=f'Test {suffix}', number=0, exponent=2, inCHF=1.0)
        db.session.add(c)
        db.session.commit()

        cr = backup_service.create_backup(
            name=f'Currency code collision test {suffix}',
            segment_types=['currencies'],
            user=admin,
        )
        assert cr.success
        bs = cr.backup_set
        for seg in bs.segments:
            backup_service.execute_backup_segment(seg)
        bs.status = 'completed'
        bs.completed_segments = bs.segments.count()
        db.session.commit()
        bs_guid = str(bs.guid)

        # Simulate a re-seeded DB: replace the currency's GUID with a fresh one,
        # keeping the code the same.
        fresh_c = Currency.query.filter_by(code=code).first()
        fresh_c.guid = uuid.uuid4()
        db.session.commit()

        # Restore — must NOT create a duplicate row for the same code
        totals = backup_service.apply_restore(bs, 'skip')

        currencies_key = next(k for k in totals if k.startswith('currencies:'))
        assert 'error' not in totals[currencies_key], (
            f'restore_currencies raised an error: {totals[currencies_key].get("error")}'
        )
        count = Currency.query.filter_by(code=code).count()
        assert count == 1, f'Expected 1 row for code {code!r}, got {count} (duplicate inserted)'
