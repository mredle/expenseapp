# coding=utf-8
"""E2E tests for the Ionic messages page (inbox, compose, send)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login


def _go_to_messages(page: Page) -> None:
    """Log in and navigate to the Messages tab."""
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/messages")
    page.wait_for_selector("ion-title:has-text('Messages')", timeout=15_000)


class TestIonicMessagesList:
    """Tests for the messages inbox."""

    def test_messages_page_renders(self, page: Page) -> None:
        """Messages page loads and shows the correct title."""
        _go_to_messages(page)
        expect(page.locator("ion-title:has-text('Messages')")).to_be_visible()

    def test_messages_list_or_empty_state(self, page: Page) -> None:
        """Page shows either message rows or the 'No messages.' empty state."""
        _go_to_messages(page)
        page.wait_for_timeout(2_000)
        has_messages = page.locator("ion-list ion-item:not(:has-text('No messages.'))").count() > 0
        has_empty = page.locator("ion-item:has-text('No messages.')").count() > 0
        assert has_messages or has_empty

    def test_compose_button_visible(self, page: Page) -> None:
        """The compose (pencil) icon button in the toolbar is visible."""
        _go_to_messages(page)
        expect(page.locator("ion-button ion-icon[name='create']")).to_be_visible()


class TestIonicComposeMessage:
    """Tests for the compose-message inline card."""

    def test_compose_button_opens_form(self, page: Page) -> None:
        """Tapping the compose button reveals the New Message card."""
        _go_to_messages(page)
        page.locator("ion-button:has(ion-icon[name='create'])").click()
        expect(page.locator("ion-card-title:has-text('New Message')")).to_be_visible(timeout=5_000)

    def test_send_disabled_without_recipient_or_body(self, page: Page) -> None:
        """Send button is disabled when no recipient or message body is filled."""
        _go_to_messages(page)
        page.locator("ion-button:has(ion-icon[name='create'])").click()
        page.wait_for_selector("ion-card-title:has-text('New Message')", timeout=5_000)
        btn = page.locator("ion-button:has-text('Send')").first
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_cancel_compose_closes_form(self, page: Page) -> None:
        """Clicking Cancel hides the compose form."""
        _go_to_messages(page)
        page.locator("ion-button:has(ion-icon[name='create'])").click()
        page.wait_for_selector("ion-card-title:has-text('New Message')", timeout=5_000)
        page.locator("ion-button:has-text('Cancel')").click()
        page.wait_for_timeout(1_000)
        assert page.locator("ion-card-title:has-text('New Message')").count() == 0
