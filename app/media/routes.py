# coding=utf-8

from flask import send_file, abort, current_app
from app.media import bp
from app.models import File
# from flask_login import login_required # (Uncomment if you want to restrict all media)

@bp.route('/<int:file_id>')
# @login_required 
def serve_file(file_id):
    file_obj = File.query.get_or_404(file_id)
    provider = file_obj.get_provider()
    
    try:
        file_stream = provider.get_file_stream(file_obj.storage_key)
    except Exception as e:
        current_app.logger.error(f"Could not read file {file_obj.id}: {str(e)}")
        abort(404)
        
    return send_file(
        file_stream,
        mimetype=file_obj.mime_type,
        as_attachment=False, # Set to True if you want it to force-download instead of displaying inline
        download_name=file_obj.original_filename
    )