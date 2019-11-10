# -*- coding: utf-8 -*-

from flask import Blueprint
from flask_restplus import Api

from .users import api as users
from .tokens import api as tokens

bp = Blueprint('apis', __name__)
apis = Api(bp,
    title='REST API',
    version='1.0',
    description='Experimental'
)

apis.add_namespace(users)
apis.add_namespace(tokens)

from app.apis import errors