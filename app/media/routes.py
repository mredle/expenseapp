# coding=utf-8
"""Media routes for serving files with Redis caching."""

from __future__ import annotations

from io import BytesIO

from flask import send_file, abort

from app.media import bp
from app.services.media_service import get_file_bytes


@bp.route('/<int:file_id>')
def serve_file(file_id: int) -> object:
    """Serve a file by its database ID, using a two-tier cache strategy.

    Tier 1: Redis in-memory cache (24 h TTL, max 5 MB per file).
    Tier 2: Browser cache via ``max_age`` (1 year).
    Falls back to the storage provider on cache miss.
    """
    result = get_file_bytes(file_id)
    if result is None:
        abort(404)

    return send_file(
        BytesIO(result.file_bytes),
        mimetype=result.mime_type,
        as_attachment=False,
        download_name=result.original_filename,
        max_age=31536000,
    )
