# coding=utf-8
"""E2E tests for the Ionic participants (event-users) page."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login


def _open_participants(page: Page) -> None:
    """Log in, open the first available event, and navigate to Participants."""
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/events")
    page.wait_for_timeout(2_000)
    items = page.locator("ion-list ion-item")
    if items.count() == 0:
        pytest.skip("No events available for participants tests.")
    items.first.click()
    page.wait_for_url("**/event-main/**", timeout=10_000)
    page.locator("ion-item:has-text('Participants')").click()
    page.wait_for_url("**/event-users**", timeout=10_000)
    page.wait_for_selector("ion-title:has-text('Participants')", timeout=10_000)


class TestIonicParticipantsList:
    """Tests for the participants list page."""

    def test_participants_page_renders(self, page: Page) -> None:
        """Participants page loads and shows the correct title."""
        _open_participants(page)
        expect(page.locator("ion-title:has-text('Participants')")).to_be_visible()

    def test_participants_list_or_empty(self, page: Page) -> None:
        """Page shows either participant rows or an empty list container."""
        _open_participants(page)
        page.wait_for_timeout(2_000)
        assert page.locator("ion-list").count() > 0

    def test_add_button_visible(self, page: Page) -> None:
        """'+' button in the toolbar is visible."""
        _open_participants(page)
        expect(page.locator("ion-button ion-icon[name='add']").first).to_be_visible()


class TestIonicAddParticipantForm:
    """Tests for the add-participant inline form."""

    def test_add_button_opens_form(self, page: Page) -> None:
        """Tapping '+' reveals the Add Participant card."""
        _open_participants(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        expect(page.locator("ion-card-title:has-text('Add Participant')")).to_be_visible(timeout=5_000)

    def test_submit_disabled_when_empty(self, page: Page) -> None:
        """Add button is disabled while required Name/Email fields are blank."""
        _open_participants(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        page.wait_for_selector("ion-card-title:has-text('Add Participant')", timeout=5_000)
        btn = page.locator("ion-button[type='submit']").first
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_cancel_closes_form(self, page: Page) -> None:
        """Clicking Cancel hides the Add Participant form."""
        _open_participants(page)
        page.locator("ion-button ion-icon[name='add']").first.click()
        page.wait_for_selector("ion-card-title:has-text('Add Participant')", timeout=5_000)
        page.locator("ion-button:has-text('Cancel')").click()
        page.wait_for_timeout(1_000)
        assert page.locator("ion-card-title:has-text('Add Participant')").count() == 0

    def test_existing_participant_row_shows_avatar(self, page: Page) -> None:
        """Any existing participant row shows an avatar slot."""
        _open_participants(page)
        page.wait_for_timeout(2_000)
        rows = page.locator("ion-item-sliding ion-item")
        if rows.count() == 0:
            pytest.skip("No participants to verify.")
        expect(rows.first.locator("ion-avatar")).to_be_visible()
