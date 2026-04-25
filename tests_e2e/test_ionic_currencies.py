# coding=utf-8
"""E2E tests for the Ionic currencies page (admin CRUD)."""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_ADMIN, E2E_ADMIN_PASSWORD, ionic_login


def _go_to_currencies(page: Page) -> None:
    """Log in as admin and navigate to the currencies tab."""
    ionic_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/currencies")
    page.wait_for_selector("ion-title:has-text('Currencies')", timeout=15_000)


class TestIonicCurrenciesList:
    """Tests for reading the currencies list."""

    def test_currencies_page_renders(self, page: Page) -> None:
        """Currencies page loads and the ion-title is visible."""
        _go_to_currencies(page)
        expect(page.locator("ion-title:has-text('Currencies')")).to_be_visible()

    def test_currencies_list_or_empty_state(self, page: Page) -> None:
        """Page shows either a list of currencies or the empty-state message."""
        _go_to_currencies(page)
        page.wait_for_timeout(2_000)
        has_items = page.locator("ion-list ion-item").count() > 0
        has_empty = page.locator("ion-item:has-text('No currencies found.')").count() > 0
        assert has_items or has_empty

    def test_add_button_visible_for_admin(self, page: Page) -> None:
        """The '+' add button is visible in the toolbar when logged in as admin."""
        _go_to_currencies(page)
        # The add button is only present when isAdmin is true
        expect(page.locator("ion-button ion-icon[name='add']").first).to_be_visible(timeout=5_000)


class TestIonicCurrencyCRUD:
    """Tests for creating and editing a currency as admin."""

    def test_open_add_form(self, page: Page) -> None:
        """Clicking the '+' button reveals the add-currency form card."""
        _go_to_currencies(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        expect(page.locator("ion-card-title:has-text('New Currency')")).to_be_visible(timeout=5_000)

    def test_add_currency_save_button_disabled_when_empty(self, page: Page) -> None:
        """Save button is disabled while required fields are empty."""
        _go_to_currencies(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        page.wait_for_selector("ion-card-title:has-text('New Currency')", timeout=5_000)
        btn = page.locator("ion-button[type='submit']").first
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_create_currency(self, page: Page) -> None:
        """Filling in the form and saving creates a new currency entry."""
        _go_to_currencies(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        page.wait_for_selector("ion-card-title:has-text('New Currency')", timeout=5_000)

        code = f"T{uuid.uuid4().hex[:2].upper()}"  # e.g. "T4A"
        page.locator("ion-input[formcontrolname='code']").click()
        page.keyboard.type(code)
        page.locator("ion-input[formcontrolname='name']").click()
        page.keyboard.type(f"Test Currency {code}")
        page.locator("ion-input[formcontrolname='inCHF']").click()
        page.keyboard.type("1.05")

        page.locator("ion-button[type='submit']").first.click()

        # Form should close and the new currency should appear in the list
        page.wait_for_selector("ion-list ion-item", timeout=10_000)
        assert page.locator(f"ion-item:has-text('{code}')").count() > 0

    def test_cancel_form(self, page: Page) -> None:
        """Clicking Cancel closes the add form without saving."""
        _go_to_currencies(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        page.wait_for_selector("ion-card-title:has-text('New Currency')", timeout=5_000)
        page.locator("ion-button:has-text('Cancel')").click()
        page.wait_for_timeout(1_000)
        assert page.locator("ion-card-title:has-text('New Currency')").count() == 0
