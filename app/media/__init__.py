# -*- coding: utf-8 -*-

from flask import Blueprint

bp = Blueprint('media', __name__)

from app.media import routes