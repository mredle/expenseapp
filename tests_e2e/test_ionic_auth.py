# coding=utf-8
"""E2E tests for the Ionic authentication flows (login, register, logout)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login


class TestIonicLogin:
    """Tests for the Ionic login page at /auth/login."""

    def test_login_page_renders(self, page: Page) -> None:
        """Login page loads and shows the username and password inputs."""
        page.goto(f"{IONIC_BASE_URL}/auth/login")
        expect(page.locator("ion-input[formcontrolname='username']")).to_be_visible(timeout=15_000)
        expect(page.locator("ion-input[formcontrolname='password']")).to_be_visible()

    def test_submit_button_disabled_when_empty(self, page: Page) -> None:
        """Sign In button is disabled when the form is empty."""
        page.goto(f"{IONIC_BASE_URL}/auth/login")
        page.wait_for_selector("ion-button[type='submit']", timeout=15_000)
        btn = page.locator("ion-button[type='submit']")
        # Ionic renders [disabled] attribute on the host element
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_successful_login_redirects(self, page: Page) -> None:
        """Entering valid credentials and submitting redirects away from /auth/login."""
        ionic_login(page, E2E_USER, E2E_PASSWORD)
        assert "/auth/login" not in page.url

    def test_invalid_credentials_stays_on_login(self, page: Page) -> None:
        """Entering wrong credentials keeps the user on the login page or shows an error."""
        page.goto(f"{IONIC_BASE_URL}/auth/login")
        page.wait_for_selector("ion-input[formcontrolname='username']", timeout=15_000)
        page.locator("ion-input[formcontrolname='username']").click()
        page.keyboard.type("nobody")
        page.locator("ion-input[formcontrolname='password']").click()
        page.keyboard.type("wrongpassword")
        page.locator("ion-button[type='submit']").click()
        # Either stays on login, or an error toast/alert appears
        page.wait_for_timeout(3_000)
        on_login = "/auth/login" in page.url
        has_error = (
            page.locator("ion-toast").count() > 0
            or page.locator("ion-alert").count() > 0
            or page.locator(".error, [color='danger']").count() > 0
        )
        assert on_login or has_error

    def test_forgot_password_link_navigates(self, page: Page) -> None:
        """'Forgot password?' button navigates to the reset-password route."""
        page.goto(f"{IONIC_BASE_URL}/auth/login")
        page.wait_for_selector("ion-button[routerlink='/auth/reset-password']", timeout=15_000)
        page.locator("ion-button[routerlink='/auth/reset-password']").click()
        page.wait_for_url("**/auth/reset-password", timeout=10_000)
        assert "/auth/reset-password" in page.url

    def test_create_account_link_navigates(self, page: Page) -> None:
        """'Create account' button navigates to the register route."""
        page.goto(f"{IONIC_BASE_URL}/auth/login")
        page.wait_for_selector("ion-button[routerlink='/auth/register']", timeout=15_000)
        page.locator("ion-button[routerlink='/auth/register']").click()
        page.wait_for_url("**/auth/register", timeout=10_000)
        assert "/auth/register" in page.url


class TestIonicRegister:
    """Tests for the Ionic registration page at /auth/register."""

    def test_register_page_renders(self, page: Page) -> None:
        """Register page loads and shows username, email and language fields."""
        page.goto(f"{IONIC_BASE_URL}/auth/register")
        expect(page.locator("ion-input[formcontrolname='username']")).to_be_visible(timeout=15_000)
        expect(page.locator("ion-input[formcontrolname='email']")).to_be_visible()

    def test_submit_disabled_when_empty(self, page: Page) -> None:
        """Create Account button is disabled when the form fields are blank."""
        page.goto(f"{IONIC_BASE_URL}/auth/register")
        page.wait_for_selector("ion-button[type='submit']", timeout=15_000)
        btn = page.locator("ion-button[type='submit']")
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_back_to_login_link(self, page: Page) -> None:
        """'Already have an account?' link navigates back to the login page."""
        page.goto(f"{IONIC_BASE_URL}/auth/register")
        page.wait_for_selector("ion-button[routerlink='/auth/login']", timeout=15_000)
        page.locator("ion-button[routerlink='/auth/login']").click()
        page.wait_for_url("**/auth/login", timeout=10_000)
        assert "/auth/login" in page.url


class TestIonicLogout:
    """Test that a logged-in user can log out via the Profile page."""

    def test_logout_returns_to_login(self, page: Page) -> None:
        """Clicking Logout on the Profile page redirects to the login page."""
        ionic_login(page, E2E_USER, E2E_PASSWORD)
        page.goto(f"{IONIC_BASE_URL}/tabs/profile")
        page.wait_for_selector("ion-button:has-text('Logout')", timeout=15_000)
        page.locator("ion-button:has-text('Logout')").click()
        page.wait_for_url("**/auth/login", timeout=10_000)
        assert "/auth/login" in page.url
