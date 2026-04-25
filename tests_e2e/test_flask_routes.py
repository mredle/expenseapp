# coding=utf-8
"""E2E tests for the core Flask HTML routes (index, currencies, users, events)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import (
    FLASK_BASE_URL,
    E2E_USER,
    E2E_PASSWORD,
    E2E_ADMIN,
    E2E_ADMIN_PASSWORD,
    flask_login,
)


class TestFlaskIndex:
    """Tests for the root / index routes."""

    def test_root_redirect(self, page: Page) -> None:
        """GET / redirects to /index or the login page for unauthenticated users."""
        page.goto(f"{FLASK_BASE_URL}/")
        page.wait_for_timeout(2_000)
        assert page.url != f"{FLASK_BASE_URL}/" or "/index" in page.url or "/auth" in page.url

    def test_index_accessible_after_login(self, page: Page) -> None:
        """Authenticated users can access the /index page."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/index")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url


class TestFlaskCurrenciesPage:
    """Tests for the /currencies admin page (admin-only)."""

    def test_currencies_page_renders_for_admin(self, page: Page) -> None:
        """Currencies page is accessible to admins and renders a list or empty state."""
        flask_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/currencies")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url
        # Either a table/list of currencies or a 'no currencies' message
        has_content = (
            page.locator("table, ul, ol, .currency, tr").count() > 0
            or page.locator("body").inner_text() != ""
        )
        assert has_content

    def test_new_currency_page_renders(self, page: Page) -> None:
        """The /new_currency form page is accessible to admins."""
        flask_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/new_currency")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url
        expect(page.locator("input[name='code'], input[id='code']").first).to_be_visible(timeout=10_000)

    def test_currencies_page_redirects_non_admin(self, page: Page) -> None:
        """Non-admin users are blocked from /currencies (redirect or 403)."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/currencies")
        page.wait_for_timeout(2_000)
        # Either redirected away or status 403 page shown
        blocked = (
            "/currencies" not in page.url
            or "403" in page.content()
            or "forbidden" in page.content().lower()
            or "not authorized" in page.content().lower()
        )
        assert blocked


class TestFlaskUsersPage:
    """Tests for the /users admin page."""

    def test_users_page_renders_for_admin(self, page: Page) -> None:
        """Users page is accessible to admins."""
        flask_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/users")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url


class TestFlaskEventRoutes:
    """Tests for the Flask /event/* HTML routes."""

    def test_event_index_renders(self, page: Page) -> None:
        """Authenticated users can access /event/index."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/event/index")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url

    def test_new_event_page_renders(self, page: Page) -> None:
        """The /event/new form is accessible to authenticated users."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/event/new")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url
        # Form should have a name input
        expect(page.locator("input[name='name'], input[id='name']").first).to_be_visible(timeout=10_000)

    def test_event_index_unauthenticated_redirects(self, page: Page) -> None:
        """Unauthenticated users are redirected away from /event/index."""
        page.goto(f"{FLASK_BASE_URL}/event/index")
        page.wait_for_timeout(2_000)
        assert "/auth" in page.url or page.locator("input[name='username']").count() > 0


class TestFlaskAdminPage:
    """Tests for the /administration page."""

    def test_administration_accessible_to_admin(self, page: Page) -> None:
        """Admin users can access the /administration dashboard."""
        flask_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/administration")
        page.wait_for_timeout(2_000)
        assert "/auth" not in page.url

    def test_administration_blocked_for_non_admin(self, page: Page) -> None:
        """Non-admin users cannot access /administration."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/administration")
        page.wait_for_timeout(2_000)
        blocked = (
            "/administration" not in page.url
            or "403" in page.content()
            or "forbidden" in page.content().lower()
        )
        assert blocked
