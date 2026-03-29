"""Main blueprint registration."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint('main', __name__)

from app.main import routes  # noqa: E402, F401 — register route handlers
