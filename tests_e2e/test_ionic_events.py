# coding=utf-8
"""E2E tests for the Ionic events list and event creation flow."""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page, expect

from tests_e2e.conftest import IONIC_BASE_URL, E2E_USER, E2E_PASSWORD, ionic_login

# Selector for the '+' add button in any Ionic toolbar.
# We target the ion-button that contains the add icon rather than the icon
# itself, because clicking the inner ion-icon is intercepted by its parent.
_ADD_BTN = "ion-button:has(ion-icon[name='add'])"


def _go_to_events(page: Page) -> None:
    """Log in and navigate to the My Events tab."""
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/events")
    page.wait_for_selector("ion-title:has-text('My Events')", timeout=15_000)


class TestIonicEventList:
    """Tests for the event list page."""

    def test_events_page_renders(self, page: Page) -> None:
        """My Events page loads with the correct title."""
        _go_to_events(page)
        expect(page.locator("ion-title:has-text('My Events')")).to_be_visible()

    def test_events_list_or_empty_state(self, page: Page) -> None:
        """Page shows either a list of events or the empty-state message."""
        _go_to_events(page)
        page.wait_for_timeout(2_000)
        has_items = page.locator("ion-list ion-item").count() > 0
        has_empty = page.locator("ion-button:has-text('Create Event')").count() > 0
        assert has_items or has_empty

    def test_add_button_visible(self, page: Page) -> None:
        """A '+' toolbar button to create new events is visible."""
        _go_to_events(page)
        expect(page.locator(_ADD_BTN).first).to_be_visible(timeout=5_000)


class TestIonicEventCreation:
    """Tests for creating a new event via the event-settings form."""

    def test_new_event_form_opens(self, page: Page) -> None:
        """Clicking the '+' button navigates to the New Event settings form."""
        _go_to_events(page)
        page.locator(_ADD_BTN).first.click()
        # Wait for the New Event title to appear (Ionic page stack may briefly
        # show both old and new page titles during transition animations).
        page.wait_for_selector("ion-title:has-text('New Event')", timeout=15_000)
        # URL must contain /event/new (new-event settings route)
        assert "/event/new" in page.url
        assert page.locator("ion-title:has-text('New Event')").count() > 0

    def test_save_disabled_when_empty(self, page: Page) -> None:
        """Create Event button is disabled while required fields are blank."""
        _go_to_events(page)
        page.locator(_ADD_BTN).first.click()
        page.wait_for_selector("ion-title:has-text('New Event')", timeout=15_000)
        btn = page.locator("ion-button[type='submit']")
        assert btn.get_attribute("disabled") is not None or btn.is_disabled()

    def test_open_event_navigates_to_detail(self, page: Page) -> None:
        """Clicking an existing event row navigates to the event-main page."""
        _go_to_events(page)
        page.wait_for_timeout(2_000)
        items = page.locator("ion-list ion-item")
        if items.count() == 0:
            pytest.skip("No events available to open.")
        items.first.click()
        # URL pattern: /event/<guid>/main
        page.wait_for_url("**/event/*/main", timeout=10_000)
        assert "/event/" in page.url and "/main" in page.url


class TestIonicEventMain:
    """Tests for the event detail (event-main) page."""

    def _open_first_event(self, page: Page) -> None:
        """Helper: open the first event in the list."""
        _go_to_events(page)
        page.wait_for_timeout(2_000)
        items = page.locator("ion-list ion-item")
        if items.count() == 0:
            pytest.skip("No events available.")
        items.first.click()
        page.wait_for_url("**/event/*/main", timeout=10_000)

    def test_event_main_shows_action_items(self, page: Page) -> None:
        """Event detail page shows the Expenses, Settlements, and Participants rows."""
        self._open_first_event(page)
        expect(page.locator("ion-item:has-text('Expenses')")).to_be_visible(timeout=10_000)
        expect(page.locator("ion-item:has-text('Settlements')")).to_be_visible()
        expect(page.locator("ion-item:has-text('Participants')")).to_be_visible()

    def test_navigate_to_expenses(self, page: Page) -> None:
        """Tapping Expenses row navigates to the expenses page."""
        self._open_first_event(page)
        page.locator("ion-item:has-text('Expenses')").click()
        page.wait_for_url("**/expenses**", timeout=10_000)
        assert "expenses" in page.url

    def test_navigate_to_settlements(self, page: Page) -> None:
        """Tapping Settlements row navigates to the settlements page."""
        self._open_first_event(page)
        page.locator("ion-item:has-text('Settlements')").click()
        page.wait_for_url("**/settlements**", timeout=10_000)
        assert "settlements" in page.url

    def test_navigate_to_participants(self, page: Page) -> None:
        """Tapping Participants row navigates to the event-users page."""
        self._open_first_event(page)
        page.locator("ion-item:has-text('Participants')").click()
        page.wait_for_url("**/users**", timeout=10_000)
        assert "users" in page.url

    def test_settings_button_navigates(self, page: Page) -> None:
        """Tapping the settings icon navigates to the event-settings page."""
        self._open_first_event(page)
        page.locator("ion-button:has(ion-icon[name='settings-outline'])").click()
        page.wait_for_url("**/settings**", timeout=10_000)
        assert "settings" in page.url
