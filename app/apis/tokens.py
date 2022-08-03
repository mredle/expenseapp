# -*- coding: utf-8 -*-

from flask import g
from flask_restx import Namespace, Resource, fields
from app import db
from app.apis.auth import basic_auth, token_auth

api = Namespace('tokens', description='Token related operations')

token = api.model('Token', {
    'token': fields.String(required=True, description='The Token'),
})

@api.route('/')
class Token(Resource):
    @basic_auth.login_required
    @api.marshal_with(token)
    def post(self):
        token = {'token': g.current_user.get_token()}
        db.session.commit()
        return token
    
    @token_auth.login_required
    def delete(self):
        g.current_user.revoke_token()
        db.session.commit()
        return '', 204
