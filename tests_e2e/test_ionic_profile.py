# coding=utf-8
"""E2E tests for the Ionic profile page (view, edit, logout)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login


def _go_to_profile(page: Page) -> None:
    """Log in and navigate to the Profile tab."""
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/profile")
    page.wait_for_selector("ion-title:has-text('Profile')", timeout=15_000)


class TestIonicProfileView:
    """Tests for the read-only profile view."""

    def test_profile_page_renders(self, page: Page) -> None:
        """Profile page loads and shows the page title."""
        _go_to_profile(page)
        expect(page.locator("ion-title:has-text('Profile')")).to_be_visible()

    def test_username_is_displayed(self, page: Page) -> None:
        """The logged-in user's username is visible somewhere on the page."""
        _go_to_profile(page)
        page.wait_for_timeout(2_000)
        # Username appears in a h2 inside an ion-item
        expect(page.locator("ion-label h2").first).to_be_visible()

    def test_avatar_is_displayed(self, page: Page) -> None:
        """An avatar image is visible in the profile header area."""
        _go_to_profile(page)
        page.wait_for_timeout(2_000)
        expect(page.locator("img[alt='avatar']")).to_be_visible()

    def test_edit_button_visible(self, page: Page) -> None:
        """The pencil icon button to toggle edit mode is in the toolbar."""
        _go_to_profile(page)
        expect(page.locator("ion-button ion-icon[name='pencil']")).to_be_visible()

    def test_logout_button_visible(self, page: Page) -> None:
        """The Logout button is visible on the profile page."""
        _go_to_profile(page)
        expect(page.locator("ion-button:has-text('Logout')")).to_be_visible()


class TestIonicProfileEdit:
    """Tests for switching into profile edit mode."""

    def test_edit_mode_shows_form(self, page: Page) -> None:
        """Clicking the pencil icon switches to edit mode with a username input."""
        _go_to_profile(page)
        page.locator("ion-button ion-icon[name='pencil']").click()
        expect(page.locator("ion-input[formcontrolname='username']")).to_be_visible(timeout=5_000)
        expect(page.locator("ion-input[formcontrolname='email']")).to_be_visible()

    def test_close_icon_exits_edit_mode(self, page: Page) -> None:
        """Clicking the close icon (×) exits edit mode."""
        _go_to_profile(page)
        page.locator("ion-button ion-icon[name='pencil']").click()
        page.wait_for_selector("ion-input[formcontrolname='username']", timeout=5_000)
        # Pencil toggled to 'close' icon
        page.locator("ion-button ion-icon[name='close']").click()
        page.wait_for_timeout(1_000)
        assert page.locator("ion-input[formcontrolname='username']").count() == 0

    def test_save_button_visible_in_edit_mode(self, page: Page) -> None:
        """Save Changes button is present while in edit mode."""
        _go_to_profile(page)
        page.locator("ion-button ion-icon[name='pencil']").click()
        expect(page.locator("ion-button[type='submit']:has-text('Save Changes')")).to_be_visible(timeout=5_000)


class TestIonicProfileSecurity:
    """Tests for the passkey section on the profile page."""

    def test_register_passkey_row_visible(self, page: Page) -> None:
        """'Register a Passkey' list item is displayed in the Security section."""
        _go_to_profile(page)
        expect(page.locator("ion-label:has-text('Register a Passkey')")).to_be_visible()
