# coding=utf-8
"""Mobile PWA blueprint — serves the Ionic/Angular build output with SPA catch-all routing."""

from __future__ import annotations

import os

from flask import Blueprint, send_from_directory

bp = Blueprint('mobile', __name__)

# Absolute path to the Ionic build output directory (mobile/www/)
_WWW_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'mobile', 'www')
)


@bp.route('/')
@bp.route('/<path:path>')
def serve(path: str = 'index.html') -> object:
    """Serve the mobile PWA.

    Tries to return the requested static file; falls back to ``index.html`` so
    that Angular's client-side router handles all unknown paths (SPA pattern).
    """
    target = os.path.join(_WWW_DIR, path)
    if os.path.isfile(target):
        return send_from_directory(_WWW_DIR, path)
    return send_from_directory(_WWW_DIR, 'index.html')
