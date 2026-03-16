# -*- coding: utf-8 -*-
from app.cli import register

def test_flush_media_cache_command(app):
    """Test that the flush-media-cache CLI command runs successfully."""
    register(app) # <--- Register the commands for the test runner!
    runner = app.test_cli_runner()
    result = runner.invoke(args=['flush-media-cache'])
    assert result.exit_code == 0, result.output
    assert "Redis media cache" in result.output

def test_db_init_command(app):
    """Test the dbinit command to ensure it seeds the DB."""
    register(app) # <--- Register the commands for the test runner!
    runner = app.test_cli_runner()
    result = runner.invoke(args=['dbinit', 'currencies', '--overwrite'])
    assert result.exit_code == 0, result.output