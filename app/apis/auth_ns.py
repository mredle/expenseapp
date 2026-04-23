# coding=utf-8
"""Auth REST API namespace: login, register, password reset, and WebAuthn endpoints."""

from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app import db
from app.apis.auth import basic_auth, token_auth
from app.apis.errors import bad_request
from app.services import auth_service

api = Namespace('auth', description='Authentication operations')

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

login_model = api.model('LoginRequest', {
    'username': fields.String(required=True, description='Username'),
    'password': fields.String(required=True, description='Password'),
})

register_model = api.model('RegisterRequest', {
    'username': fields.String(required=True, description='Username'),
    'email': fields.String(required=True, description='Email address'),
    'locale': fields.String(description='Preferred locale', default='en'),
})

register_response = api.model('RegisterResponse', {
    'guid': fields.String(description='User GUID'),
    'username': fields.String(description='Username'),
    'email': fields.String(description='Email'),
})

reset_request_model = api.model('ResetPasswordRequest', {
    'email': fields.String(required=True, description='Email address'),
})

set_password_model = api.model('SetPasswordRequest', {
    'token': fields.String(required=True, description='Password reset JWT token'),
    'password': fields.String(required=True, description='New password'),
})

token_response = api.model('TokenResponse', {
    'token': fields.String(description='API bearer token'),
})

webauthn_options_response = api.model('WebAuthnOptionsResponse', {
    'options': fields.String(description='JSON-encoded WebAuthn options'),
    'session_id': fields.String(description='Challenge GUID for verification'),
})

webauthn_register_verify_model = api.model('WebAuthnRegisterVerify', {
    'session_id': fields.String(required=True, description='Challenge GUID'),
    'credential': fields.Raw(required=True, description='WebAuthn credential JSON'),
})

webauthn_auth_verify_model = api.model('WebAuthnAuthVerify', {
    'session_id': fields.String(required=True, description='Challenge GUID'),
    'credential': fields.Raw(required=True, description='WebAuthn credential JSON'),
})

auth_result = api.model('AuthResult', {
    'token': fields.String(description='API bearer token'),
    'user_guid': fields.String(description='Authenticated user GUID'),
    'username': fields.String(description='Username'),
})

message_response = api.model('MessageResponse', {
    'message': fields.String(description='Status message'),
})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route('/login')
class Login(Resource):
    """Authenticate with username and password, receive an API token."""

    @api.expect(login_model)
    @api.marshal_with(auth_result, code=200)
    @api.response(401, 'Invalid credentials')
    def post(self) -> dict | tuple:
        """Authenticate and return an API token."""
        data = request.get_json() or {}
        username = data.get('username', '')
        password = data.get('password', '')

        if not username or not password:
            return bad_request('Username and password are required')

        result = auth_service.authenticate_password(username, password)
        if not result.success or result.user is None:
            return {'error': 'Invalid credentials'}, 401

        token = result.user.get_token()
        db.session.commit()
        return {
            'token': token,
            'user_guid': str(result.user.guid),
            'username': result.user.username,
        }


@api.route('/register')
class Register(Resource):
    """Register a new user account."""

    @api.expect(register_model)
    @api.marshal_with(register_response, code=201)
    @api.response(400, 'Validation error')
    def post(self) -> tuple:
        """Create a new user account."""
        data = request.get_json() or {}
        username = data.get('username', '')
        email = data.get('email', '')
        locale = data.get('locale', 'en')

        if not username or not email:
            return bad_request('Username and email are required')

        from app.models import User
        if User.query.filter_by(username=username).first():
            return bad_request('Please use a different username')
        if User.query.filter_by(email=email).first():
            return bad_request('Please use a different email address')

        result = auth_service.register_user(username, email, locale)
        db.session.commit()
        return {
            'guid': str(result.user.guid),
            'username': result.user.username,
            'email': result.user.email,
        }, 201


@api.route('/reset-password')
class ResetPassword(Resource):
    """Request a password reset email."""

    @api.expect(reset_request_model)
    @api.marshal_with(message_response)
    def post(self) -> dict:
        """Request a password reset.

        Always returns success to prevent email enumeration.
        """
        data = request.get_json() or {}
        email = data.get('email', '')
        if email:
            auth_service.request_password_reset(email)
        return {'message': 'If the email is registered, a reset link has been sent'}


@api.route('/set-password')
class SetPassword(Resource):
    """Set a new password using a reset token."""

    @api.expect(set_password_model)
    @api.marshal_with(message_response)
    @api.response(400, 'Invalid or expired token')
    def post(self) -> dict | tuple:
        """Validate reset token and set a new password."""
        data = request.get_json() or {}
        token = data.get('token', '')
        password = data.get('password', '')

        if not token or not password:
            return bad_request('Token and password are required')

        user = auth_service.verify_reset_token(token)
        if not user:
            return bad_request('Invalid or expired reset token')

        auth_service.set_user_password(user, password)
        db.session.commit()
        return {'message': 'Password has been reset'}


@api.route('/webauthn/register/options')
class WebAuthnRegisterOptions(Resource):
    """Generate WebAuthn registration options for the authenticated user."""

    @token_auth.login_required
    @api.marshal_with(webauthn_options_response)
    def post(self) -> dict | tuple:
        """Generate WebAuthn registration options."""
        result = auth_service.generate_webauthn_registration_options(g.current_user)
        if not result.success:
            return bad_request(result.error or 'Failed to generate options')
        return {
            'options': result.options_json,
            'session_id': result.challenge_guid,
        }


@api.route('/webauthn/register/verify')
class WebAuthnRegisterVerify(Resource):
    """Verify a WebAuthn registration response."""

    @token_auth.login_required
    @api.expect(webauthn_register_verify_model)
    @api.marshal_with(message_response)
    @api.response(400, 'Verification failed')
    def post(self) -> dict | tuple:
        """Verify WebAuthn registration credential."""
        data = request.get_json() or {}
        session_id = data.get('session_id', '')
        credential = data.get('credential')

        if not session_id or not credential:
            return bad_request('session_id and credential are required')

        result = auth_service.verify_webauthn_registration(
            g.current_user, session_id, credential,
        )
        if not result.success:
            return bad_request(result.error or 'Verification failed')
        return {'message': 'Credential registered successfully'}


@api.route('/webauthn/authenticate/options')
class WebAuthnAuthenticateOptions(Resource):
    """Generate WebAuthn authentication options (discoverable credentials)."""

    @api.marshal_with(webauthn_options_response)
    def post(self) -> dict | tuple:
        """Generate WebAuthn authentication options."""
        result = auth_service.generate_webauthn_authentication_options()
        if not result.success:
            return bad_request(result.error or 'Failed to generate options')
        return {
            'options': result.options_json,
            'session_id': result.challenge_guid,
        }


@api.route('/webauthn/authenticate/verify')
class WebAuthnAuthenticateVerify(Resource):
    """Verify a WebAuthn authentication response and return an API token."""

    @api.expect(webauthn_auth_verify_model)
    @api.marshal_with(auth_result)
    @api.response(401, 'Authentication failed')
    def post(self) -> dict | tuple:
        """Verify WebAuthn authentication credential and return a token."""
        data = request.get_json() or {}
        session_id = data.get('session_id', '')
        credential = data.get('credential')

        if not session_id or not credential:
            return bad_request('session_id and credential are required')

        result = auth_service.verify_webauthn_authentication(session_id, credential)
        if not result.success or result.user is None:
            return {'error': 'Authentication failed'}, 401

        token = result.user.get_token()
        db.session.commit()
        return {
            'token': token,
            'user_guid': str(result.user.guid),
            'username': result.user.username,
        }
