# coding=utf-8
"""REST API blueprint setup: Flask-RESTX Api instance and namespace registration."""

from __future__ import annotations

from flask import Blueprint
from flask_restx import Api

from .admin_ns import api as admin
from .auth_ns import api as auth
from .currencies_ns import api as currencies
from .events_ns import api as events
from .media_ns import api as media
from .messages_ns import api as messages
from .tokens import api as tokens
from .users import api as users

bp = Blueprint('apis', __name__)
apis = Api(
    bp,
    title='REST API',
    version='1.0',
    description='Experimental',
)

apis.add_namespace(admin)
apis.add_namespace(auth)
apis.add_namespace(currencies)
apis.add_namespace(events)
apis.add_namespace(media)
apis.add_namespace(messages)
apis.add_namespace(tokens)
apis.add_namespace(users)

from app.apis import errors  # noqa: E402, F401
