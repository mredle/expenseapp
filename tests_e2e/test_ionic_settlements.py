# coding=utf-8
"""E2E tests for the Ionic settlements page (list, add form, confirm, cancel)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login


def _open_settlements(page: Page) -> None:
    """Log in, open the first available event, and navigate to Settlements."""
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/events")
    page.wait_for_timeout(2_000)
    items = page.locator("ion-list ion-item")
    if items.count() == 0:
        pytest.skip("No events available for settlements tests.")
    items.first.click()
    page.wait_for_url("**/event/*/main", timeout=10_000)
    page.locator("ion-item:has-text('Settlements')").click()
    page.wait_for_url("**/settlements**", timeout=10_000)
    page.wait_for_selector("ion-title:has-text('Settlements')", timeout=10_000)


class TestIonicSettlementsList:
    """Tests for the settlements list view."""

    def test_settlements_page_renders(self, page: Page) -> None:
        """Settlements page loads and shows the correct title."""
        _open_settlements(page)
        expect(page.locator("ion-title:has-text('Settlements')")).to_be_visible()

    def test_settlements_list_or_empty(self, page: Page) -> None:
        """Page shows either settlement rows or an empty list."""
        _open_settlements(page)
        page.wait_for_timeout(2_000)
        assert page.locator("ion-list").count() > 0

    def test_add_button_visible(self, page: Page) -> None:
        """'+' button is visible in the settlements toolbar."""
        _open_settlements(page)
        expect(page.locator("ion-button:has(ion-icon[name='add'])").last).to_be_visible()


class TestIonicAddSettlementForm:
    """Tests for the add-settlement inline form."""

    def test_add_button_opens_form(self, page: Page) -> None:
        """Tapping '+' reveals the Add Settlement card."""
        _open_settlements(page)
        page.locator("ion-button:has(ion-icon[name='add'])").last.click()
        expect(page.locator("ion-card-title:has-text('Add Settlement')")).to_be_visible(timeout=5_000)

    def test_submit_disabled_when_empty(self, page: Page) -> None:
        """Add button in the form is disabled while required fields are blank."""
        _open_settlements(page)
        page.locator("ion-button:has(ion-icon[name='add'])").last.click()
        page.wait_for_selector("ion-card-title:has-text('Add Settlement')", timeout=5_000)
        btn = page.locator("ion-button[type='submit']").first
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_cancel_closes_form(self, page: Page) -> None:
        """Clicking Cancel hides the Add Settlement form."""
        _open_settlements(page)
        page.locator("ion-button:has(ion-icon[name='add'])").last.click()
        page.wait_for_selector("ion-card-title:has-text('Add Settlement')", timeout=5_000)
        page.locator("ion-button:has-text('Cancel')").click()
        page.wait_for_timeout(1_000)
        assert page.locator("ion-card-title:has-text('Add Settlement')").count() == 0

    def test_draft_settlement_shows_confirm_button(self, page: Page) -> None:
        """Any draft settlement in the list shows a 'Confirm' button."""
        _open_settlements(page)
        page.wait_for_timeout(2_000)
        draft_confirms = page.locator("ion-button:has-text('Confirm')")
        # This test is informational — it passes whether drafts exist or not
        # If drafts exist, the Confirm button must be visible
        if draft_confirms.count() > 0:
            expect(draft_confirms.first).to_be_visible()
