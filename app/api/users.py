# -*- coding: utf-8 -*-

from flask import jsonify, request
from flask_restplus import Resource
from app import db
from app.api import api
from app.models import User
from app.api.errors import bad_request
from app.api.auth import token_auth


@api.route('/users')
class ApiUserList(Resource):
    @token_auth.login_required
    def get(self):
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = User.to_collection_dict(User.query, page, per_page, 'api.api_user_list')
        return jsonify(data)
    
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
        response = jsonify(user.to_dict())
        response.status_code = 201
        response.headers['Location'] = api.url_for(ApiUserList, id=user.id)
        return response


@api.route('/user/<int:id>')
class ApiUser(Resource):
    @token_auth.login_required
    def get(self, id):
        return jsonify(User.query.get_or_404(id).to_dict())

    @token_auth.login_required
    def put(self, id):
        user = User.query.get_or_404(id)
        data = request.get_json() or {}
        if 'username' in data and data['username'] != user.username and \
                User.query.filter_by(username=data['username']).first():
            return bad_request('please use a different username')
        if 'email' in data and data['email'] != user.email and \
                User.query.filter_by(email=data['email']).first():
            return bad_request('please use a different email address')
        user.from_dict(data, new_user=False)
        db.session.commit()
        return jsonify(user.to_dict())
