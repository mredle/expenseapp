"""Auth blueprint registration."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint('auth', __name__)

from app.auth import routes  # noqa: E402, F401 — register route handlers
