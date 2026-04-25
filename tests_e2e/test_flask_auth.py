# coding=utf-8
"""E2E tests for the Flask HTML authentication routes (login, register, logout)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests_e2e.conftest import FLASK_BASE_URL, E2E_USER, E2E_PASSWORD, flask_login


class TestFlaskLoginPage:
    """Tests for the /auth/authenticate_password HTML route."""

    def test_login_page_renders(self, page: Page) -> None:
        """Login page loads and shows username + password inputs."""
        page.goto(f"{FLASK_BASE_URL}/auth/authenticate_password")
        expect(page.locator("input[name='username']")).to_be_visible(timeout=15_000)
        expect(page.locator("input[name='password']")).to_be_visible()

    def test_successful_login_redirects(self, page: Page) -> None:
        """Valid credentials redirect away from the login page."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        assert "/auth/authenticate_password" not in page.url

    def test_invalid_credentials_shows_error(self, page: Page) -> None:
        """Invalid credentials keep the user on the login page or show an error."""
        page.goto(f"{FLASK_BASE_URL}/auth/authenticate_password")
        page.wait_for_selector("input[name='username']", timeout=15_000)
        page.fill("input[name='username']", "nobody")
        page.fill("input[name='password']", "wrongpassword")
        page.locator("input[type='submit'], button[type='submit']").first.click()
        page.wait_for_timeout(2_000)
        on_login = "/auth/authenticate_password" in page.url
        has_error = (
            page.locator(".error, .alert, .flash, [class*='danger'], [class*='error']").count() > 0
        )
        assert on_login or has_error

    def test_login_page_has_register_link(self, page: Page) -> None:
        """Login page contains a link to the registration page."""
        page.goto(f"{FLASK_BASE_URL}/auth/authenticate_password")
        page.wait_for_selector("a[href*='register']", timeout=15_000)
        expect(page.locator("a[href*='register']").first).to_be_visible()


class TestFlaskRegisterPage:
    """Tests for the /auth/register HTML route."""

    def test_register_page_renders(self, page: Page) -> None:
        """Registration page loads and shows the expected form fields."""
        page.goto(f"{FLASK_BASE_URL}/auth/register")
        page.wait_for_selector("input[name='username']", timeout=15_000)
        expect(page.locator("input[name='username']")).to_be_visible()
        expect(page.locator("input[name='email']")).to_be_visible()

    def test_register_page_submit_button_visible(self, page: Page) -> None:
        """The submit button is present on the registration form."""
        page.goto(f"{FLASK_BASE_URL}/auth/register")
        page.wait_for_selector("input[type='submit'], button[type='submit']", timeout=15_000)
        expect(page.locator("input[type='submit'], button[type='submit']").first).to_be_visible()


class TestFlaskLogout:
    """Tests for the /auth/logout route."""

    def test_logout_redirects_to_login(self, page: Page) -> None:
        """After logging out, the user is redirected to the login page."""
        flask_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{FLASK_BASE_URL}/auth/logout")
        page.wait_for_timeout(2_000)
        # After logout Flask should redirect to login or root
        assert (
            "/auth" in page.url
            or "/index" in page.url
            or page.url == f"{FLASK_BASE_URL}/"
            or page.url == f"{FLASK_BASE_URL}/index"
        )

    def test_protected_route_redirects_after_logout(self, page: Page) -> None:
        """A logged-out user accessing a protected route is redirected to login."""
        # Navigate directly to the currencies admin page without logging in
        page.goto(f"{FLASK_BASE_URL}/currencies")
        page.wait_for_timeout(2_000)
        assert "/auth" in page.url or page.locator("input[name='username']").count() > 0
