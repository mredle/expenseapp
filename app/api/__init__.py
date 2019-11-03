# -*- coding: utf-8 -*-

from flask import Blueprint
from flask_restplus import Api

bp = Blueprint('api', __name__)
api = Api(bp)

from app.api import users, errors, tokens