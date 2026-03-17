# coding=utf-8

import redis
from io import BytesIO
from flask import send_file, current_app, abort
from app import db
from app.media import bp
from app.models import File
# from flask_login import login_required # (Uncomment if you want to restrict all media)

def get_redis_connection():
    """Helper to fetch the Redis connection from your existing config."""
    # If your app attaches redis directly (like current_app.redis), use that.
    # Otherwise, instantiate a connection using your existing environment variables:
    if hasattr(current_app, 'redis'):
        return current_app.redis
        
    return redis.Redis(
        host=current_app.config.get('REDIS_HOST', 'localhost'),
        port=current_app.config.get('REDIS_PORT', 6379),
        db=current_app.config.get('REDIS_DB', 0),
        password=current_app.config.get('REDIS_PASSWORD')
    )

@bp.route('/<int:file_id>')
# @login_required 
def serve_file(file_id):
    file_obj = db.session.get(File, file_id)
    if file_obj is None:
        abort(404)
    
    r = get_redis_connection()
    cache_key = f"media_cache:{file_obj.id}"
    
    # ---------------------------------------------------------
    # TIER 1: Try to fetch directly from Redis (In-Memory RAM)
    # ---------------------------------------------------------
    try:
        cached_data = r.get(cache_key)
        if cached_data:
            return send_file(
                BytesIO(cached_data),
                mimetype=file_obj.mime_type,
                as_attachment=False,
                download_name=file_obj.original_filename,
                max_age=31536000 # Browser Cache (1 year)
            )
    except Exception as e:
        current_app.logger.warning(f"Redis cache read failed: {e}")

    # ---------------------------------------------------------
    # CACHE MISS: Fetch from Storage Provider (S3/MinIO)
    # ---------------------------------------------------------
    provider = file_obj.get_provider()
    
    try:
        file_stream = provider.get_file_stream(file_obj.storage_key)
        file_bytes = file_stream.read() # Read the raw bytes into memory
    except Exception as e:
        current_app.logger.error(f"Could not read file {file_obj.id}: {str(e)}")
        abort(404)
        
    # ---------------------------------------------------------
    # SAVE TO CACHE: Store in Redis for the next request
    # ---------------------------------------------------------
    try:
        # Prevent Redis from running out of RAM by only caching files smaller than 5MB
        if len(file_bytes) < 5 * 1024 * 1024: 
            # setex stores the data with an expiration time (86400 seconds = 24 hours)
            r.setex(cache_key, 86400, file_bytes)
    except Exception as e:
        current_app.logger.warning(f"Redis cache write failed: {e}")
        
    # Serve the newly fetched file
    return send_file(
        BytesIO(file_bytes),
        mimetype=file_obj.mime_type,
        as_attachment=False,
        download_name=file_obj.original_filename,
        max_age=31536000 # TIER 2: Browser Cache (1 year)
    )