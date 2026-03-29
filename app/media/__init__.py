# -*- coding: utf-8 -*-
"""Media blueprint for serving and processing uploaded images."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint('media', __name__)

from app.media import routes  # noqa: E402, F401
