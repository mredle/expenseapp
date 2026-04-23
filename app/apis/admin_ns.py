# coding=utf-8
"""Admin REST API namespace: dashboard, logs, tasks, and statistics."""

from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.apis.auth import token_auth
from app.apis.errors import bad_request
from app.services import main_service

api = Namespace('admin', description='Admin operations')

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

log_model = api.model('Log', {
    'id': fields.Integer(description='Log ID'),
    'severity': fields.String(description='Severity level'),
    'module': fields.String(description='Module name'),
    'msg_type': fields.String(description='Message type'),
    'msg': fields.String(description='Log message'),
    'date': fields.String(description='Timestamp'),
    'username': fields.String(description='User who triggered the log'),
})

log_detail_model = api.model('LogDetail', {
    'id': fields.Integer(description='Log ID'),
    'severity': fields.String(description='Severity level'),
    'module': fields.String(description='Module name'),
    'msg_type': fields.String(description='Message type'),
    'msg': fields.String(description='Log message'),
    'trace': fields.String(description='Stack trace'),
    'date': fields.String(description='Timestamp'),
    'username': fields.String(description='User who triggered the log'),
})

log_list_model = api.model('LogList', {
    'items': fields.List(fields.Nested(log_model), description='Log entries'),
    'total': fields.Integer(description='Total entries'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page'),
})

task_model = api.model('Task', {
    'id': fields.String(description='Task ID'),
    'name': fields.String(description='Task function name'),
    'description': fields.String(description='Human-readable description'),
    'complete': fields.Boolean(description='Whether the task is complete'),
    'progress': fields.Integer(description='Progress percentage (0-100)'),
    'username': fields.String(description='User who launched the task'),
})

task_list_model = api.model('TaskList', {
    'items': fields.List(fields.Nested(task_model), description='Background tasks'),
    'total': fields.Integer(description='Total tasks'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page'),
})

launch_task_model = api.model('LaunchTaskInput', {
    'key': fields.String(required=True, description='Task key (WASTE_TIME, CHECK_CURRENCIES, UPDATE_CURRENCIES, TYPE_ERROR)'),
    'amount': fields.Integer(description='Amount parameter (for WASTE_TIME / TYPE_ERROR)'),
    'source': fields.String(description='Source parameter (for UPDATE_CURRENCIES)'),
})

stat_model = api.model('Stat', {
    'label': fields.String(description='Statistic label'),
    'count': fields.Integer(description='Count'),
})

stats_response = api.model('StatsResponse', {
    'items': fields.List(fields.Nested(stat_model), description='Statistics'),
})

message_response = api.model('AdminMessageResponse', {
    'message': fields.String(description='Status message'),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_to_dict(log_entry: object) -> dict:
    """Serialise a Log model to a dict."""
    return {
        'id': log_entry.id,
        'severity': log_entry.severity,
        'module': log_entry.module,
        'msg_type': log_entry.msg_type,
        'msg': log_entry.msg,
        'date': log_entry.date.isoformat() if log_entry.date else None,
        'username': log_entry.user.username if log_entry.user else None,
    }


def _log_detail_to_dict(log_entry: object) -> dict:
    """Serialise a Log model with trace to a dict."""
    d = _log_to_dict(log_entry)
    d['trace'] = log_entry.trace
    return d


def _task_to_dict(task: object) -> dict:
    """Serialise a Task model to a dict."""
    return {
        'id': task.id,
        'name': task.name,
        'description': task.description,
        'complete': task.complete,
        'progress': task.get_progress(),
        'username': task.user.username if task.user else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route('/logs')
class LogList(Resource):
    """List log entries."""

    @token_auth.login_required
    @api.marshal_with(log_list_model)
    def get(self) -> dict:
        """Return a paginated list of log entries.

        Admins see all logs; regular users see only their own.
        Query params: ``page``, ``per_page``, ``severity``.
        """
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        severity = request.args.get('severity')

        result = main_service.list_logs(
            page=page,
            severity=severity,
            user=g.current_user,
            is_admin=g.current_user.is_admin,
            per_page=per_page,
        )
        return {
            'items': [_log_to_dict(log) for log in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }


@api.route('/logs/<int:log_id>')
class LogDetail(Resource):
    """Read a single log entry with its stack trace."""

    @token_auth.login_required
    @api.marshal_with(log_detail_model)
    @api.response(403, 'Access denied')
    def get(self, log_id: int) -> dict | tuple:
        """Return a single log entry including its trace."""
        log_entry = main_service.get_log_trace(log_id)
        if not log_entry.can_view(g.current_user):
            return {'error': 'Access denied'}, 403
        return _log_detail_to_dict(log_entry)


@api.route('/tasks')
class TaskList(Resource):
    """List and launch background tasks."""

    @token_auth.login_required
    @api.marshal_with(task_list_model)
    def get(self) -> dict:
        """Return a paginated list of background tasks.

        Admins see all tasks; regular users see only their own.
        Query params: ``page``, ``per_page``, ``complete`` (true/false).
        """
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        complete_str = request.args.get('complete')
        complete = None
        if complete_str is not None:
            complete = complete_str.lower() == 'true'

        result = main_service.list_tasks(
            page=page,
            complete=complete,
            user=g.current_user,
            is_admin=g.current_user.is_admin,
            per_page=per_page,
        )
        return {
            'items': [_task_to_dict(t) for t in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(launch_task_model)
    @api.marshal_with(message_response)
    @api.response(400, 'Invalid task key')
    def post(self) -> dict | tuple:
        """Launch a background task."""
        data = request.get_json() or {}
        key = data.get('key', '')
        if not key:
            return bad_request('Task key is required')

        kwargs = {}
        if 'amount' in data:
            kwargs['amount'] = data['amount']
        if 'source' in data:
            kwargs['source'] = data['source']

        result = main_service.launch_task(g.current_user, key, **kwargs)
        if not result.success:
            return bad_request(result.error or 'Failed to launch task')
        return {'message': f'Task {key} launched'}


@api.route('/tasks/<guid>')
class TaskDetail(Resource):
    """Delete a completed task."""

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(403, 'Admin required')
    def delete(self, guid: str) -> dict | tuple:
        """Remove a completed task (admin only)."""
        if not g.current_user.is_admin:
            return {'error': 'Admin privileges required'}, 403

        main_service.remove_task(guid)
        return {'message': 'Task removed'}


@api.route('/statistics')
class Statistics(Resource):
    """Return model statistics for the admin dashboard."""

    @token_auth.login_required
    @api.marshal_with(stats_response)
    def get(self) -> dict:
        """Return aggregate model statistics.

        Admins see all models; regular users see a subset.
        """
        stats = main_service.get_statistics(g.current_user, g.current_user.is_admin)
        return {
            'items': [{'label': label, 'count': count} for label, count in stats],
        }
