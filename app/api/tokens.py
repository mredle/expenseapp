# -*- coding: utf-8 -*-

from flask import jsonify, g
from flask_restplus import Resource
from app import db
from app.api import api
from app.api.auth import basic_auth, token_auth

@api.route('/tokens')
class Token(Resource):
    @basic_auth.login_required
    def post(self):
        token = g.current_user.get_token()
        db.session.commit()
        return jsonify({'token': token})
    
    @token_auth.login_required
    def delete(self):
        g.current_user.revoke_token()
        db.session.commit()
        return '', 204
