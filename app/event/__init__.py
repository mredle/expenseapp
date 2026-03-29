# -*- coding: utf-8 -*-
"""Event blueprint for managing shared expenses, settlements, and event users."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint('event', __name__)

from app.event import routes  # noqa: E402, F401
