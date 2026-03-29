# coding=utf-8
"""Media routes for serving files with Redis caching."""

from __future__ import annotations

from io import BytesIO

import redis
from flask import send_file, current_app, abort

from app import db
from app.media import bp
from app.models import File


def get_redis_connection() -> redis.Redis:
    """Return the Redis connection from the app or create one from config."""
    if hasattr(current_app, 'redis'):
        return current_app.redis

    return redis.Redis(
        host=current_app.config.get('REDIS_HOST', 'localhost'),
        port=current_app.config.get('REDIS_PORT', 6379),
        db=current_app.config.get('REDIS_DB', 0),
        password=current_app.config.get('REDIS_PASSWORD'),
    )


@bp.route('/<int:file_id>')
def serve_file(file_id: int) -> object:
    """Serve a file by its database ID, using a two-tier cache strategy.

    Tier 1: Redis in-memory cache (24 h TTL, max 5 MB per file).
    Tier 2: Browser cache via ``max_age`` (1 year).
    Falls back to the storage provider on cache miss.
    """
    file_obj = db.session.get(File, file_id)
    if file_obj is None:
        abort(404)

    r = get_redis_connection()
    cache_key = f"media_cache:{file_obj.id}"

    # Tier 1 -- Redis
    try:
        cached_data = r.get(cache_key)
        if cached_data:
            return send_file(
                BytesIO(cached_data),
                mimetype=file_obj.mime_type,
                as_attachment=False,
                download_name=file_obj.original_filename,
                max_age=31536000,
            )
    except Exception as e:
        current_app.logger.warning(f"Redis cache read failed: {e}")

    # Cache miss -- fetch from storage provider
    provider = file_obj.get_provider()

    try:
        file_stream = provider.get_file_stream(file_obj.storage_key)
        file_bytes = file_stream.read()
    except Exception as e:
        current_app.logger.error(f"Could not read file {file_obj.id}: {e}")
        abort(404)

    # Store in Redis for subsequent requests (files < 5 MB only)
    try:
        if len(file_bytes) < 5 * 1024 * 1024:
            r.setex(cache_key, 86400, file_bytes)
    except Exception as e:
        current_app.logger.warning(f"Redis cache write failed: {e}")

    # Tier 2 -- browser cache
    return send_file(
        BytesIO(file_bytes),
        mimetype=file_obj.mime_type,
        as_attachment=False,
        download_name=file_obj.original_filename,
        max_age=31536000,
    )
