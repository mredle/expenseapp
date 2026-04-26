# coding=utf-8
"""E2E tests for the Ionic expenses page (list, add form, cancel)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login


def _open_expenses(page: Page) -> None:
    """Log in, open the first available event, and navigate to Expenses."""
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/events")
    page.wait_for_timeout(2_000)
    items = page.locator("ion-list ion-item")
    if items.count() == 0:
        pytest.skip("No events available for expenses tests.")
    items.first.click()
    page.wait_for_url("**/event/*/main", timeout=10_000)
    page.locator("ion-item:has-text('Expenses')").click()
    page.wait_for_url("**/expenses**", timeout=10_000)
    page.wait_for_selector("ion-title:has-text('Expenses')", timeout=10_000)


class TestIonicExpensesList:
    """Tests for the expenses list view."""

    def test_expenses_page_renders(self, page: Page) -> None:
        """Expenses page loads with the correct title."""
        _open_expenses(page)
        expect(page.locator("ion-title:has-text('Expenses')")).to_be_visible()

    def test_filter_segment_present(self, page: Page) -> None:
        """All / Mine segment buttons are visible."""
        _open_expenses(page)
        expect(page.locator("ion-segment-button:has-text('All')")).to_be_visible()
        expect(page.locator("ion-segment-button:has-text('Mine')")).to_be_visible()

    def test_expenses_list_or_empty(self, page: Page) -> None:
        """Page shows either expense rows or an empty list."""
        _open_expenses(page)
        page.wait_for_timeout(2_000)
        # Either items or the list container exists (empty list is still valid)
        assert page.locator("ion-list").count() > 0


class TestIonicAddExpenseForm:
    """Tests for the add-expense inline form."""

    def test_add_button_opens_form(self, page: Page) -> None:
        """Tapping the '+' button reveals the Add Expense card."""
        _open_expenses(page)
        page.locator("ion-button:has(ion-icon[name='add'])").last.click()
        expect(page.locator("ion-card-title:has-text('Add Expense')")).to_be_visible(timeout=5_000)

    def test_add_button_disabled_when_form_empty(self, page: Page) -> None:
        """'Add Expense' submit button is disabled while required fields are blank."""
        _open_expenses(page)
        page.locator("ion-button:has(ion-icon[name='add'])").last.click()
        page.wait_for_selector("ion-card-title:has-text('Add Expense')", timeout=5_000)
        btn = page.locator("ion-button[type='submit']").first
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_cancel_closes_form(self, page: Page) -> None:
        """Clicking Cancel hides the Add Expense form."""
        _open_expenses(page)
        page.locator("ion-button:has(ion-icon[name='add'])").last.click()
        page.wait_for_selector("ion-card-title:has-text('Add Expense')", timeout=5_000)
        page.locator("ion-button:has-text('Cancel')").click()
        page.wait_for_timeout(1_000)
        assert page.locator("ion-card-title:has-text('Add Expense')").count() == 0

    def test_mine_filter_switch(self, page: Page) -> None:
        """Switching to 'Mine' segment triggers a reload (no crash)."""
        _open_expenses(page)
        page.locator("ion-segment-button:has-text('Mine')").click()
        page.wait_for_timeout(2_000)
        # Page should still be on expenses — no navigation error
        assert "expenses" in page.url
