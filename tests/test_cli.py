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
