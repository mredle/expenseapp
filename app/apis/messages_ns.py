# coding=utf-8
"""Messages REST API namespace: list, send, and notifications."""

from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.apis.auth import token_auth
from app.apis.errors import bad_request
from app.services import main_service

api = Namespace('messages', description='Messaging operations')

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

message_model = api.model('Message', {
    'id': fields.Integer(description='Message ID'),
    'body': fields.String(description='Message body'),
    'timestamp': fields.String(description='Sent timestamp'),
    'sender': fields.String(description='Sender username'),
    'recipient': fields.String(description='Recipient username'),
})

message_list_model = api.model('MessageList', {
    'items': fields.List(fields.Nested(message_model), description='Messages'),
    'total': fields.Integer(description='Total messages'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page'),
})

send_message_model = api.model('SendMessageInput', {
    'recipient_id': fields.Integer(required=True, description='Recipient user ID'),
    'body': fields.String(required=True, description='Message body'),
})

notification_model = api.model('Notification', {
    'name': fields.String(description='Notification name'),
    'data': fields.Raw(description='Notification payload'),
    'timestamp': fields.Float(description='POSIX timestamp'),
})

notification_list_model = api.model('NotificationList', {
    'items': fields.List(fields.Nested(notification_model), description='Notifications'),
})

status_response = api.model('MessagesStatusResponse', {
    'message': fields.String(description='Status message'),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _message_to_dict(msg: object) -> dict:
    """Serialise a Message model to a dict."""
    return {
        'id': msg.id,
        'body': msg.body,
        'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
        'sender': msg.author.username if msg.author else None,
        'recipient': msg.recipient.username if msg.recipient else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route('/')
class MessageList(Resource):
    """List messages or send a new one."""

    @token_auth.login_required
    @api.marshal_with(message_list_model)
    def get(self) -> dict:
        """Return a paginated list of sent and received messages.

        Also marks messages as read.
        Query params: ``page``, ``per_page``.
        """
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)

        main_service.mark_messages_read(g.current_user)

        result = main_service.list_messages(g.current_user, page, per_page)
        return {
            'items': [_message_to_dict(m) for m in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(send_message_model)
    @api.marshal_with(message_model, code=201)
    @api.response(400, 'Validation error')
    def post(self) -> tuple:
        """Send a direct message to another user."""
        data = request.get_json() or {}
        recipient_id = data.get('recipient_id')
        body = data.get('body', '')

        if not recipient_id or not body:
            return bad_request('recipient_id and body are required')

        result = main_service.send_message(g.current_user, recipient_id, body)
        if not result.success:
            return bad_request(result.error or 'Failed to send message')
        return _message_to_dict(result.message), 201


@api.route('/notifications')
class NotificationList(Resource):
    """Poll for new notifications."""

    @token_auth.login_required
    @api.marshal_with(notification_list_model)
    def get(self) -> dict:
        """Return notifications newer than the ``since`` timestamp.

        Query param: ``since`` (POSIX float, defaults to 0).
        """
        since = request.args.get('since', 0, type=float)
        notifications = main_service.get_notifications(g.current_user, since)
        return {'items': notifications}
