# -*- coding: utf-8 -*-
"""Token REST API namespace: issue, refresh, and revoke authentication tokens."""

from __future__ import annotations

from flask import g
from flask_restx import Namespace, Resource, fields

from app import db
from app.apis.auth import basic_auth, token_auth

api = Namespace('tokens', description='Token related operations')

token = api.model('Token', {
    'token': fields.String(required=True, description='The Token'),
    'expires_at': fields.String(description='Token expiry as an ISO-8601 UTC timestamp'),
})


@api.route('/')
class Token(Resource):
    """Issue or revoke an API authentication token."""

    @basic_auth.login_required
    @api.marshal_with(token)
    def post(self) -> dict:
        """Issue a new token for the authenticated user."""
        issued = g.current_user.get_token()
        expires_at = g.current_user.get_token_expiration()
        db.session.commit()
        return {
            'token': issued,
            'expires_at': expires_at.isoformat() if expires_at else None,
        }

    @token_auth.login_required
    def delete(self) -> tuple:
        """Revoke the current user's token."""
        g.current_user.revoke_token()
        db.session.commit()
        return '', 204


@api.route('/refresh')
class TokenRefresh(Resource):
    """Renew an authentication token before it expires."""

    @token_auth.login_required
    @api.marshal_with(token)
    @api.doc(security='Bearer')
    @api.response(200, 'Token refreshed')
    @api.response(401, 'Missing, invalid or expired token')
    def post(self) -> dict:
        """Issue a fresh token for the currently authenticated user.

        Requires a still-valid token: an expired token fails authentication, so
        the client must refresh before expiry (or log in again). The token is
        rotated rather than merely extended, so the previous value stops working
        immediately.
        """
        issued = g.current_user.get_token(force=True)
        expires_at = g.current_user.get_token_expiration()
        db.session.commit()
        return {
            'token': issued,
            'expires_at': expires_at.isoformat() if expires_at else None,
        }
