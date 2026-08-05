# -*- coding: utf-8 -*-
"""Tests for Flask CLI commands (flush-media-cache, dbinit)."""

from __future__ import annotations

from app.cli import register


def test_flush_media_cache_command(app) -> None:
    """Test that the flush-media-cache CLI command runs successfully."""
    register(app)
    runner = app.test_cli_runner()
    result = runner.invoke(args=['flush-media-cache'])
    assert result.exit_code == 0, result.output
    assert "Redis media cache" in result.output


def test_db_init_command(app) -> None:
    """Test the dbinit command to ensure it seeds the DB."""
    register(app)
    runner = app.test_cli_runner()
    result = runner.invoke(args=['dbinit', 'currencies', '--overwrite'])
    assert result.exit_code == 0, result.output


def test_purge_read_error_files_reports_nothing_when_clean(app) -> None:
    """purge-read-error-files reports no findings when no file is flagged."""
    register(app)
    runner = app.test_cli_runner()
    result = runner.invoke(args=['dbmaint', 'purge-read-error-files'])
    assert result.exit_code == 0, result.output
    assert 'No files flagged' in result.output


def test_purge_read_error_files_dry_run_keeps_rows(app) -> None:
    """Without --delete the command lists flagged files but keeps them."""
    import uuid

    from app import db
    from app.models import File

    register(app)
    with app.app_context():
        file_obj = File(
            original_filename='broken.png',
            storage_backend='local',
            storage_key=f'missing/{uuid.uuid4().hex}.png',
            mime_type='image/png',
            file_size=1,
        )
        file_obj.read_error = True
        db.session.add(file_obj)
        db.session.commit()
        file_id = file_obj.id

    runner = app.test_cli_runner()
    result = runner.invoke(args=['dbmaint', 'purge-read-error-files'])

    assert result.exit_code == 0, result.output
    assert 'Dry-run' in result.output
    with app.app_context():
        assert db.session.get(File, file_id) is not None


def test_purge_read_error_files_delete_removes_rows(app) -> None:
    """With --delete the flagged rows are removed, unflagged ones are kept."""
    import uuid

    from app import db
    from app.models import File

    register(app)
    with app.app_context():
        broken = File(
            original_filename='broken.png',
            storage_backend='local',
            storage_key=f'missing/{uuid.uuid4().hex}.png',
            mime_type='image/png',
            file_size=1,
        )
        broken.read_error = True
        healthy = File(
            original_filename='fine.png',
            storage_backend='local',
            storage_key=f'ok/{uuid.uuid4().hex}.png',
            mime_type='image/png',
            file_size=1,
        )
        db.session.add_all([broken, healthy])
        db.session.commit()
        broken_id, healthy_id = broken.id, healthy.id

    runner = app.test_cli_runner()
    result = runner.invoke(args=['dbmaint', 'purge-read-error-files', '--delete'])

    assert result.exit_code == 0, result.output
    with app.app_context():
        assert db.session.get(File, broken_id) is None
        assert db.session.get(File, healthy_id) is not None
