# -*- coding: utf-8 -*-
"""Error-handling blueprint for application-wide HTTP error pages."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint('errors', __name__)

from app.errors import handlers  # noqa: E402, F401
