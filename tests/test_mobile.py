# coding=utf-8
"""Tests for the mobile PWA blueprint (/mobile/)."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient


def test_mobile_root_returns_html(app: Flask, client: FlaskClient) -> None:
    """GET /mobile/ returns 200 and the Angular index.html shell."""
    response = client.get('/mobile/')
    assert response.status_code == 200
    data = response.data.decode()
    assert '<base href="/mobile/">' in data
    assert '<app-root>' in data


def test_mobile_unknown_path_falls_back_to_index(app: Flask, client: FlaskClient) -> None:
    """GET /mobile/<any-spa-path> returns the index.html shell for client-side routing."""
    for path in ('/mobile/tabs/events', '/mobile/auth/login', '/mobile/some/deep/route'):
        response = client.get(path)
        assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"
        data = response.data.decode()
        assert '<app-root>' in data, f"Expected SPA shell for {path}"


def test_mobile_static_asset_served(app: Flask, client: FlaskClient) -> None:
    """GET /mobile/manifest.webmanifest serves the PWA manifest file."""
    response = client.get('/mobile/manifest.webmanifest')
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert 'name' in data


def test_mobile_ngsw_json_served(app: Flask, client: FlaskClient) -> None:
    """GET /mobile/ngsw.json serves the Angular service worker config."""
    response = client.get('/mobile/ngsw.json')
    assert response.status_code == 200


def test_mobile_root_no_auth_required(app: Flask, client: FlaskClient) -> None:
    """GET /mobile/ is publicly accessible without a login session."""
    # client fixture is an unauthenticated client
    response = client.get('/mobile/')
    assert response.status_code == 200
