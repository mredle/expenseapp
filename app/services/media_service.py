# coding=utf-8
"""Media service — business logic for file serving with Redis caching."""

from __future__ import annotations

from dataclasses import dataclass

import redis
from flask import current_app

from app import db
from app.models import File


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    """Resolved file metadata and binary content."""

    file_bytes: bytes
    mime_type: str
    original_filename: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_redis_connection() -> redis.Redis:
    """Return the Redis connection from the app or create one from config."""
    if hasattr(current_app, 'redis'):
        return current_app.redis

    return redis.Redis(
        host=current_app.config.get('REDIS_HOST', 'localhost'),
        port=current_app.config.get('REDIS_PORT', 6379),
        db=current_app.config.get('REDIS_DB', 0),
        password=current_app.config.get('REDIS_PASSWORD'),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_file_bytes(file_id: int) -> FileResult | None:
    """Retrieve file content by database ID using a two-tier cache strategy.

    Tier 1: Redis in-memory cache (24 h TTL, max 5 MB per file).
    Falls back to the storage provider on cache miss.

    Returns ``None`` when the file ID does not exist.
    """
    file_obj = db.session.get(File, file_id)
    if file_obj is None:
        return None

    r = _get_redis_connection()
    cache_key = f"media_cache:{file_obj.id}"

    # Tier 1 — Redis
    try:
        cached_data = r.get(cache_key)
        if cached_data:
            return FileResult(
                file_bytes=cached_data,
                mime_type=file_obj.mime_type,
                original_filename=file_obj.original_filename,
            )
    except Exception as e:
        current_app.logger.warning(f"Redis cache read failed: {e}")

    # Cache miss — fetch from storage provider
    provider = file_obj.get_provider()

    try:
        file_stream = provider.get_file_stream(file_obj.storage_key)
        file_bytes = file_stream.read()
    except Exception as e:
        current_app.logger.error(f"Could not read file {file_obj.id}: {e}")
        return None

    # Store in Redis for subsequent requests (files < 5 MB only)
    try:
        if len(file_bytes) < 5 * 1024 * 1024:
            r.setex(cache_key, 86400, file_bytes)
    except Exception as e:
        current_app.logger.warning(f"Redis cache write failed: {e}")

    return FileResult(
        file_bytes=file_bytes,
        mime_type=file_obj.mime_type,
        original_filename=file_obj.original_filename,
    )
