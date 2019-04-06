# -*- coding: utf-8 -*-

from flask import Blueprint

bp = Blueprint('event', __name__)

from app.event import routes