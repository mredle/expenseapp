# coding=utf-8
"""Backups REST API namespace: create, list, retrieve, delete, export, import and restore backups."""

from __future__ import annotations

import io

from flask import g, request, send_file
from flask_restx import Namespace, Resource, fields

from app.apis.auth import token_auth
from app.apis.errors import bad_request
from app.services import backup_service

api = Namespace('backups', description='Backup and restore operations')

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

segment_model = api.model('BackupSegment', {
    'segment_type': fields.String(description='Segment type (currencies, users, event, logs, system)'),
    'segment_key': fields.String(description='Segment key (event GUID for event segments)'),
    'segment_label': fields.String(description='Human-readable segment label'),
    'status': fields.String(description='Segment status'),
    'record_count': fields.Integer(description='Number of primary records'),
    'file_size': fields.Integer(description='Segment file size in bytes'),
    'checksum': fields.String(description='SHA-256 checksum of segment data'),
    'error_message': fields.String(description='Error message if segment failed'),
})

backup_set_model = api.model('BackupSet', {
    'guid': fields.String(description='Backup set GUID'),
    'name': fields.String(description='Backup name'),
    'backup_type': fields.String(description='full or partial'),
    'status': fields.String(description='Backup status'),
    'total_segments': fields.Integer(description='Total segment count'),
    'completed_segments': fields.Integer(description='Completed segment count'),
    'storage_backend': fields.String(description='Storage backend name'),
    'created_at': fields.String(description='Creation timestamp'),
    'created_by': fields.String(description='Username of creator'),
    'segments': fields.List(fields.Nested(segment_model), description='Segment details'),
})

backup_list_model = api.model('BackupList', {
    'items': fields.List(fields.Nested(backup_set_model), description='Backup sets'),
    'total': fields.Integer(description='Total backup sets'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page'),
})

create_backup_model = api.model('CreateBackupInput', {
    'name': fields.String(required=True, description='Backup name'),
    'segment_types': fields.List(
        fields.String,
        description='Segment types to include (default: all)',
    ),
    'event_guids': fields.List(fields.String, description='Specific event GUIDs (partial backup)'),
})

restore_input_model = api.model('RestoreInput', {
    'strategy': fields.String(
        description='Conflict strategy: skip (default) or overwrite',
        default='skip',
    ),
})

message_model = api.model('BackupMessageResponse', {
    'message': fields.String(description='Status message'),
    'guid': fields.String(description='Backup set GUID (where applicable)'),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _segment_to_dict(seg: object) -> dict:
    """Serialise a BackupSegment to a dict."""
    return {
        'segment_type': seg.segment_type,
        'segment_key': seg.segment_key,
        'segment_label': seg.segment_label,
        'status': seg.status,
        'record_count': seg.record_count,
        'file_size': seg.file_size,
        'checksum': seg.checksum,
        'error_message': seg.error_message,
    }


def _backup_set_to_dict(bs: object) -> dict:
    """Serialise a BackupSet to a dict."""
    return {
        'guid': str(bs.guid),
        'name': bs.name,
        'backup_type': bs.backup_type,
        'status': bs.status,
        'total_segments': bs.total_segments,
        'completed_segments': bs.completed_segments,
        'storage_backend': bs.storage_backend,
        'created_at': bs.db_created_at.isoformat() if bs.db_created_at else None,
        'created_by': bs.db_created_by,
        'segments': [_segment_to_dict(s) for s in bs.segments],
    }


def _require_admin() -> tuple | None:
    """Return a 403 response tuple if the current user is not an admin, else None."""
    if not g.current_user.is_admin:
        return {'error': 'Admin privileges required'}, 403
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route('')
class BackupList(Resource):
    """List backup sets and create new ones."""

    @token_auth.login_required
    @api.marshal_with(backup_list_model)
    @api.response(403, 'Admin required')
    def get(self) -> dict | tuple:
        """Return a paginated list of backup sets (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        page = request.args.get('page', 1, type=int)
        result = backup_service.list_backups(page)
        return {
            'items': [_backup_set_to_dict(bs) for bs in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(create_backup_model)
    @api.marshal_with(message_model)
    @api.response(400, 'Validation error')
    @api.response(403, 'Admin required')
    def post(self) -> dict | tuple:
        """Create a new backup set and launch the backup task (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        data = request.get_json() or {}
        name = data.get('name', '')
        if not name:
            return bad_request('Backup name is required')
        segment_types = data.get('segment_types') or ['currencies', 'users', 'events', 'logs', 'system']
        event_guids = data.get('event_guids') or None

        result = backup_service.create_backup(
            name=name,
            segment_types=segment_types,
            user=g.current_user,
            event_guids=event_guids,
        )
        if not result.success:
            return bad_request(result.error or 'Failed to create backup')

        g.current_user.launch_task(
            'run_backup',
            f'Running backup {name}...',
            backup_set_guid=str(result.backup_set.guid),
        )
        from app import db
        db.session.commit()
        return {'message': f'Backup started: {name}', 'guid': str(result.backup_set.guid)}


@api.route('/<guid>')
class BackupDetail(Resource):
    """Retrieve or delete a specific backup set."""

    @token_auth.login_required
    @api.marshal_with(backup_set_model)
    @api.response(403, 'Admin required')
    @api.response(404, 'Not found')
    def get(self, guid: str) -> dict | tuple:
        """Return details for one backup set (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        bs = backup_service.get_backup(guid)
        if bs is None:
            return {'error': 'Backup not found'}, 404
        return _backup_set_to_dict(bs)

    @token_auth.login_required
    @api.marshal_with(message_model)
    @api.response(403, 'Admin required')
    @api.response(404, 'Not found')
    def delete(self, guid: str) -> dict | tuple:
        """Delete a backup set and its segment files (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        result = backup_service.delete_backup(guid)
        if not result.success:
            return {'error': result.error}, 404
        return {'message': 'Backup deleted', 'guid': guid}


@api.route('/<guid>/download')
class BackupDownload(Resource):
    """Download a backup set as a .tar.gz archive."""

    @token_auth.login_required
    @api.response(403, 'Admin required')
    @api.response(404, 'Not found')
    def get(self, guid: str):
        """Stream the backup as a .tar.gz file (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        result = backup_service.export_backup(guid)
        if not result.success:
            return {'error': result.error}, 404
        return send_file(
            io.BytesIO(result.archive_bytes),
            mimetype='application/gzip',
            as_attachment=True,
            download_name=result.filename,
        )


@api.route('/<guid>/restore')
class BackupRestore(Resource):
    """Launch an async restore from a backup set."""

    @token_auth.login_required
    @api.expect(restore_input_model)
    @api.marshal_with(message_model)
    @api.response(403, 'Admin required')
    @api.response(404, 'Not found')
    def post(self, guid: str) -> dict | tuple:
        """Launch a background restore task for this backup set (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        bs = backup_service.get_backup(guid)
        if bs is None:
            return {'error': 'Backup not found'}, 404
        data = request.get_json() or {}
        strategy = data.get('strategy', 'skip')
        if strategy not in ('skip', 'overwrite'):
            return bad_request('strategy must be "skip" or "overwrite"')
        g.current_user.launch_task(
            'run_restore',
            f'Restoring backup {bs.name}...',
            backup_set_guid=guid,
            strategy=strategy,
        )
        from app import db
        db.session.commit()
        return {'message': f'Restore started for backup: {bs.name}', 'guid': guid}


@api.route('/import')
class BackupImport(Resource):
    """Upload and import a .tar.gz backup archive."""

    @token_auth.login_required
    @api.marshal_with(message_model)
    @api.response(400, 'Invalid archive')
    @api.response(403, 'Admin required')
    def post(self) -> dict | tuple:
        """Import a backup archive uploaded via multipart/form-data (admin only)."""
        denied = _require_admin()
        if denied:
            return denied
        if 'archive' not in request.files:
            return bad_request('No archive file provided')
        archive_file = request.files['archive']
        result = backup_service.import_backup(archive_file.stream, g.current_user)
        if not result.success:
            return bad_request(result.error or 'Import failed')
        return {
            'message': f'Backup imported: {result.backup_set.name}',
            'guid': str(result.backup_set.guid),
        }
