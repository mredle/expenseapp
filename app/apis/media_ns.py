# coding=utf-8
"""Media REST API namespace: serve files, view and rotate images."""

from __future__ import annotations

from io import BytesIO

from flask import send_file
from flask_restx import Namespace, Resource, fields

from app.apis.auth import token_auth
from app.services import main_service, media_service

api = Namespace('media', description='Media file operations')

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

image_model = api.model('Image', {
    'guid': fields.String(description='Image GUID'),
    'width': fields.Integer(description='Image width in pixels'),
    'height': fields.Integer(description='Image height in pixels'),
    'rotate': fields.Integer(description='Current rotation in degrees'),
    'format': fields.String(description='Image format (e.g. JPEG, PNG)'),
    'url': fields.String(description='URL to serve the image'),
})

rotate_input = api.model('RotateInput', {
    'degree': fields.Integer(required=True, description='Degrees to rotate (90, 180, 270)'),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _image_to_dict(image: object) -> dict:
    """Serialise an Image model to a dict."""
    return {
        'guid': str(image.guid),
        'width': image.width,
        'height': image.height,
        'rotate': image.rotate,
        'format': image.format,
        'url': image.get_url(),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route('/files/<int:file_id>')
class FileServe(Resource):
    """Serve a file by database ID."""

    def get(self, file_id: int) -> object:
        """Serve the raw file content with appropriate MIME type.

        Uses Redis caching (24h TTL) and browser caching (1 year).
        No authentication required — files are referenced by opaque ID.
        """
        result = media_service.get_file_bytes(file_id)
        if result is None:
            api.abort(404, 'File not found')

        return send_file(
            BytesIO(result.file_bytes),
            mimetype=result.mime_type,
            as_attachment=False,
            download_name=result.original_filename,
            max_age=31536000,
        )


@api.route('/images/<guid>')
class ImageDetail(Resource):
    """Read image metadata by GUID."""

    @token_auth.login_required
    @api.marshal_with(image_model)
    def get(self, guid: str) -> dict:
        """Return image metadata."""
        image = main_service.get_image(guid)
        return _image_to_dict(image)


@api.route('/images/<guid>/rotate')
class ImageRotate(Resource):
    """Rotate an image by a specified degree."""

    @token_auth.login_required
    @api.expect(rotate_input)
    @api.marshal_with(image_model)
    @api.response(400, 'Invalid rotation degree')
    def post(self, guid: str) -> dict | tuple:
        """Rotate an image. Degree must be 90, 180, or 270."""
        from flask import request

        data = request.get_json() or {}
        degree = data.get('degree', 0)

        if degree not in (90, 180, 270):
            from app.apis.errors import bad_request
            return bad_request('Degree must be 90, 180, or 270')

        image = main_service.rotate_image(guid, degree)
        return _image_to_dict(image)
