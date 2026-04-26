# coding=utf-8
"""E2E tests for the core Flask HTML routes (index, currencies, users, events)."""

from __future__ import annotations

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
        page.goto(f"{FLASK_BASE_URL}/", wait_until="networkidle", timeout=15_000)
        assert page.url != f"{FLASK_BASE_URL}/" or "/index" in page.url or "/auth" in page.url

    def test_index_accessible_after_login(self, flask_user_page: Page) -> None:
        """Authenticated users can access the /index page."""
        flask_user_page.goto(f"{FLASK_BASE_URL}/index", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_user_page.url


class TestFlaskCurrenciesPage:
    """Tests for the /currencies page."""

    def test_currencies_page_renders_for_admin(self, flask_admin_page: Page) -> None:
        """Currencies page is accessible to admins and renders a list or empty state."""
        flask_admin_page.goto(f"{FLASK_BASE_URL}/currencies", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_admin_page.url
        has_content = (
            flask_admin_page.locator("table, ul, ol, .currency, tr").count() > 0
            or flask_admin_page.locator("body").inner_text() != ""
        )
        assert has_content

    def test_new_currency_page_renders(self, flask_admin_page: Page) -> None:
        """The /new_currency form page is accessible to admins."""
        flask_admin_page.goto(f"{FLASK_BASE_URL}/new_currency", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_admin_page.url
        expect(flask_admin_page.locator("input[name='code'], input[id='code']").first).to_be_visible(timeout=10_000)

    def test_currencies_page_accessible_to_non_admin(self, flask_user_page: Page) -> None:
        """Non-admin users can view /currencies (read-only list; create/edit/delete is admin-only)."""
        flask_user_page.goto(f"{FLASK_BASE_URL}/currencies", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_user_page.url
        assert "/currencies" in flask_user_page.url


class TestFlaskUsersPage:
    """Tests for the /users admin page."""

    def test_users_page_renders_for_admin(self, flask_admin_page: Page) -> None:
        """Users page is accessible to admins."""
        flask_admin_page.goto(f"{FLASK_BASE_URL}/users", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_admin_page.url


class TestFlaskEventRoutes:
    """Tests for the Flask /event/* HTML routes."""

    def test_event_index_renders(self, flask_user_page: Page) -> None:
        """Authenticated users can access /event/index."""
        flask_user_page.goto(f"{FLASK_BASE_URL}/event/index", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_user_page.url

    def test_new_event_page_renders(self, flask_user_page: Page) -> None:
        """The /event/new form is accessible to authenticated users."""
        flask_user_page.goto(f"{FLASK_BASE_URL}/event/new", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_user_page.url
        expect(flask_user_page.locator("input[name='name'], input[id='name']").first).to_be_visible(timeout=10_000)

    def test_event_index_unauthenticated_redirects(self, page: Page) -> None:
        """Unauthenticated users are redirected away from /event/index."""
        page.goto(f"{FLASK_BASE_URL}/event/index", wait_until="networkidle", timeout=10_000)
        assert "/auth" in page.url or page.locator("input[name='username']").count() > 0


class TestFlaskAdminPage:
    """Tests for the /administration page."""

    def test_administration_accessible_to_admin(self, flask_admin_page: Page) -> None:
        """Admin users can access the /administration dashboard."""
        flask_admin_page.goto(f"{FLASK_BASE_URL}/administration", wait_until="networkidle", timeout=10_000)
        assert "/auth" not in flask_admin_page.url

    def test_administration_blocked_for_non_admin(self, flask_user_page: Page) -> None:
        """Non-admin users cannot access /administration."""
        flask_user_page.goto(f"{FLASK_BASE_URL}/administration", wait_until="networkidle", timeout=10_000)
        blocked = (
            "/administration" not in flask_user_page.url
            or "403" in flask_user_page.content()
            or "forbidden" in flask_user_page.content().lower()
        )
        assert blocked
