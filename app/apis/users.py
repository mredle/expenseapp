# -*- coding: utf-8 -*-

from flask import request
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
    @token_auth.login_required
    @api.marshal_with(collection)
    def get(self):
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = User.to_collection_dict(User.query, page, per_page, 'apis.users_api_user_list')
        return data
    
    @api.marshal_with(user)
    @api.expect(user)
    def post(self):
        data = request.get_json() or {}
        if 'username' not in data or 'email' not in data or 'password' not in data:
            return bad_request('must include username, email and password fields')
        if User.query.filter_by(username=data['username']).first():
            return bad_request('please use a different username')
        if User.query.filter_by(email=data['email']).first():
            return bad_request('please use a different email address')
        user = User(username=data['username'], email=data['email'])
        user.from_dict(data, new_user=True)
        db.session.add(user)
        db.session.commit()
        response = user.to_dict()
        response.status_code = 201
        response.headers['Location'] = api.url_for(ApiUserList, guid=user.guid)
        return response


@api.route('/<guid>')
class ApiUser(Resource):
    @token_auth.login_required
    @api.marshal_with(user)
    def get(self, guid):
        return User.get_by_guid_or_404(guid).to_dict()

    @token_auth.login_required
    @api.expect(user)
    def put(self, guid):
        user = User.get_by_guid_or_404(guid)
        data = request.get_json() or {}
        if 'username' in data and data['username'] != user.username and \
                User.query.filter_by(username=data['username']).first():
            return bad_request('please use a different username')
        if 'email' in data and data['email'] != user.email and \
                User.query.filter_by(email=data['email']).first():
            return bad_request('please use a different email address')
        user.from_dict(data, new_user=False)
        db.session.commit()
        return user.to_dict()
