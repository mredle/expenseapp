# -*- coding: utf-8 -*-
"""Users REST API namespace: list, create, read, and update users."""

from __future__ import annotations

from flask import request, url_for
from flask_restx import Namespace, Resource, fields

from app import db
from app.models import User
from app.apis.errors import bad_request
from app.apis.auth import token_auth

api = Namespace('users', description='User API')

link_fields = api.model('links', {
    'self': fields.String(description='Link to the user'),
    'avatar': fields.String(description='Link to the avatar'),
})

user = api.model('User', {
    'id': fields.String(required=True, description='ID'),
    'username': fields.String(required=True, description='The username'),
    'email': fields.String(description='The email address'),
    'last_seen': fields.String(description='When user accessed his page last'),
    'about_me': fields.String(description='About the user'),
    'post_count': fields.Integer(description='Number of posts'),
    '_links': fields.Nested(link_fields, description='User relevant links'),
})

meta_fields = api.model('meta', {
    'page': fields.Integer(required=True, description='Actual page'),
    'per_page': fields.Integer(required=True, description='Items per page'),
    'total_pages': fields.Integer(required=True, description='Total pages'),
    'total_items': fields.Integer(required=True, description='Total items'),
})

page_link_fields = api.model('page_links', {
    'self': fields.String(required=True, description='Link to this page'),
    'next': fields.String(required=True, description='Link to the next page'),
    'prev': fields.String(required=True, description='Link to the previous page'),
})

collection = api.model('Collection', {
    'items': fields.List(fields.Nested(user), required=True, description='List of items'),
    '_meta': fields.Nested(meta_fields, required=True, description='Metadata about resource'),
    '_links': fields.Nested(page_link_fields, required=True, description='Links to navigate between pages'),
})


@api.route('/')
class ApiUserList(Resource):
    """List all users or create a new one."""

    @token_auth.login_required
    @api.marshal_with(collection)
    def get(self) -> dict:
        """Return a paginated collection of all users."""
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = User.to_collection_dict(User.query, page, per_page, 'apis.users_api_user_list')
        return data

    # BUG FIX: added @token_auth.login_required — this endpoint was
    # previously unauthenticated, allowing anyone to create users.
    @token_auth.login_required
    @api.marshal_with(user, code=201)
    @api.expect(user)
    def post(self) -> tuple:
        """Create a new user."""
        data = request.get_json() or {}
        if 'username' not in data or 'email' not in data or 'password' not in data:
            return bad_request('must include username, email and password fields')
        if User.query.filter_by(username=data['username']).first():
            return bad_request('please use a different username')
        if User.query.filter_by(email=data['email']).first():
            return bad_request('please use a different email address')
        # BUG FIX: User() was missing the required locale argument.
        new_user = User(
            username=data['username'],
            email=data['email'],
            locale=data.get('locale', 'en'),
        )
        new_user.from_dict(data, new_user=True)
        db.session.add(new_user)
        db.session.commit()
        # BUG FIX: user.to_dict() returns a plain dict — cannot set
        # .status_code or .headers on it.  Return a (body, status, headers)
        # tuple instead, which Flask-RESTX handles correctly.
        return new_user.to_dict(), 201, {'Location': url_for('apis.users_api_user', guid=new_user.guid)}


@api.route('/<guid>')
class ApiUser(Resource):
    """Read or update a single user by GUID."""

    @token_auth.login_required
    @api.marshal_with(user)
    def get(self, guid: str) -> dict:
        """Return a single user."""
        return User.get_by_guid_or_404(guid).to_dict()

    @token_auth.login_required
    @api.expect(user)
    def put(self, guid: str) -> dict:
        """Update an existing user."""
        target_user = User.get_by_guid_or_404(guid)
        data = request.get_json() or {}
        if 'username' in data and data['username'] != target_user.username and \
                User.query.filter_by(username=data['username']).first():
            return bad_request('please use a different username')
        if 'email' in data and data['email'] != target_user.email and \
                User.query.filter_by(email=data['email']).first():
            return bad_request('please use a different email address')
        target_user.from_dict(data, new_user=False)
        db.session.commit()
        return target_user.to_dict()
