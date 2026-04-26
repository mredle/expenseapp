# coding=utf-8
"""Seed E2E test data: currency → event → participant → expense → settlement.

This file is named with the ``00`` prefix so pytest discovers and runs it
*before* all other ``test_ionic_*.py`` files (alphabetical order).  Each test
creates one piece of data that subsequent Ionic E2E tests depend on.

All interactions go through the Ionic web app UI so that the Playwright test
stack itself verifies the creation flows as well as seeding the data.

Execution order within this file:
  1. test_seed_currency     — create CHF currency as admin
  2. test_seed_event        — create "E2E Test Event" as User0
  3. test_seed_participant  — add a second participant to the event as User0
  4. test_seed_expense      — add a CHF expense to the event as User0
  5. test_seed_settlement   — add a draft CHF settlement to the event as User0

A module-level ``_STATE`` dict carries the event GUID between tests in this
file (extracted from the URL after event creation).
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests_e2e.conftest import (
    IONIC_BASE_URL,
    E2E_ADMIN,
    E2E_ADMIN_PASSWORD,
    E2E_USER,
    E2E_PASSWORD,
    ionic_login,
)

# ---------------------------------------------------------------------------
# Shared state between seed tests
# ---------------------------------------------------------------------------

_STATE: dict[str, str] = {}  # populated with 'event_guid' by test_seed_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ADD_BTN = "ion-button:has(ion-icon[name='add'])"


def _select_ion_option(page: Page, form_control: str, option_text: str) -> None:
    """Click an ion-select, wait for the ion-alert overlay, pick one option, confirm.

    Works for single-select ion-select elements whose options default to the
    Ionic ``alert`` interface.
    """
    page.locator(f"ion-select[formcontrolname='{form_control}']").click()
    page.locator("ion-alert").wait_for(state="visible", timeout=10_000)
    page.locator("ion-alert button").filter(has_text=option_text).first.click()
    # The OK / Confirm button is always the last button in the alert's button group
    page.locator("ion-alert .alert-button-group button").last.click()
    page.locator("ion-alert").wait_for(state="hidden", timeout=10_000)


def _select_ion_options_multi(page: Page, form_control: str, option_texts: list[str]) -> None:
    """Click an ion-select, wait for the ion-alert overlay, pick multiple options, confirm.

    Works for ``[multiple]="true"`` ion-select elements (checkbox-style alert).
    """
    page.locator(f"ion-select[formcontrolname='{form_control}']").click()
    page.locator("ion-alert").wait_for(state="visible", timeout=10_000)
    for text in option_texts:
        page.locator("ion-alert button").filter(has_text=text).first.click()
    page.locator("ion-alert .alert-button-group button").last.click()
    page.locator("ion-alert").wait_for(state="hidden", timeout=10_000)


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------


def test_seed_currency(page: Page) -> None:
    """Create a CHF currency as admin via the Ionic currencies UI.

    Skips gracefully if CHF already exists so the suite is idempotent.
    """
    ionic_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/currencies", wait_until="networkidle")
    page.wait_for_selector("ion-title:has-text('Currencies')", timeout=15_000)
    page.wait_for_timeout(2_000)

    # If CHF already exists, no action needed
    if page.locator("ion-item:has-text('CHF')").count() > 0:
        return

    # Open the add form
    page.locator(_ADD_BTN).first.click()
    page.wait_for_selector("ion-card-title:has-text('New Currency')", timeout=10_000)

    # Fill required fields (all are plain ion-input, no ion-select)
    page.locator("ion-input[formcontrolname='code']").locator("input").fill("CHF")
    page.locator("ion-input[formcontrolname='name']").locator("input").fill("Swiss Franc")
    page.locator("ion-input[formcontrolname='number']").locator("input").fill("756")
    page.locator("ion-input[formcontrolname='exponent']").locator("input").fill("2")
    page.locator("ion-input[formcontrolname='inCHF']").locator("input").fill("1.0")

    page.locator("ion-button[type='submit']").first.click()

    # Form closes and the new currency appears in the list
    page.wait_for_selector("ion-list ion-item", timeout=10_000)
    expect(page.locator("ion-item:has-text('CHF')").first).to_be_visible(timeout=10_000)


def test_seed_event(page: Page) -> None:
    """Create an 'E2E Test Event' as User0 via the Ionic event-settings UI.

    Skips the creation step if an event already exists (idempotent), but
    always stores the first event's GUID in ``_STATE`` for later seed tests.
    """
    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/tabs/events", wait_until="networkidle")
    page.wait_for_selector("ion-title:has-text('My Events')", timeout=15_000)
    page.wait_for_timeout(2_000)

    # If an event already exists, capture its GUID and move on
    if page.locator("ion-list ion-item").count() > 0:
        page.locator("ion-list ion-item").first.click()
        page.wait_for_url("**/event/*/main", timeout=10_000)
        match = re.search(r"/event/([^/]+)/main", page.url)
        assert match, f"Could not parse event GUID from URL: {page.url}"
        _STATE["event_guid"] = match.group(1)
        return

    # Navigate to new-event settings form (via the + button)
    page.locator(_ADD_BTN).first.click()
    page.wait_for_selector("ion-title:has-text('New Event')", timeout=15_000)

    # Fill the name field
    page.locator("ion-input[formcontrolname='name']").locator("input").fill("E2E Test Event")

    # Fill the date field
    page.locator("ion-input[formcontrolname='date']").locator("input").fill("2026-06-01")

    # Select base currency (single ion-select → ion-alert → CHF option)
    _select_ion_option(page, "base_currency_id", "CHF")

    # Select allowed currencies (multi ion-select → ion-alert → CHF option)
    _select_ion_options_multi(page, "currency_ids", ["CHF"])

    # Submit — navigates to /event/<guid>/main on success
    page.locator("ion-button[type='submit']").first.click()
    page.wait_for_url("**/event/*/main", timeout=15_000)

    # Extract and store the event GUID from the URL
    match = re.search(r"/event/([^/]+)/main", page.url)
    assert match, f"Could not parse event GUID from URL after creation: {page.url}"
    _STATE["event_guid"] = match.group(1)


def test_seed_participant(page: Page) -> None:
    """Add a second participant ('SeedParticipant') to the seeded event.

    Skips if SeedParticipant already exists (idempotent).
    """
    assert _STATE.get("event_guid"), "event_guid not set — test_seed_event must run first"
    guid = _STATE["event_guid"]

    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/event/{guid}/users", wait_until="networkidle")
    page.wait_for_selector("ion-title:has-text('Participants')", timeout=15_000)
    page.wait_for_timeout(2_000)

    # Idempotency: skip if SeedParticipant is already present
    if page.locator("ion-item:has-text('SeedParticipant')").count() > 0:
        return

    # Open add form
    page.locator(_ADD_BTN).last.click()
    page.wait_for_selector("ion-card-title:has-text('Add Participant')", timeout=10_000)

    page.locator("ion-input[formcontrolname='username']").locator("input").fill("SeedParticipant")
    page.locator("ion-input[formcontrolname='email']").locator("input").fill("seedparticipant@e2e.test")

    page.locator("ion-button[type='submit']").first.click()

    # Form closes and new participant row appears
    page.wait_for_timeout(2_000)
    expect(page.locator("ion-item:has-text('SeedParticipant')").first).to_be_visible(timeout=10_000)


def test_seed_expense(page: Page) -> None:
    """Add a CHF 25.00 expense to the seeded event.

    At least one expense must exist so expense-list tests can verify list
    rendering vs. empty state.  Idempotent: skips if any expense already exists.
    """
    assert _STATE.get("event_guid"), "event_guid not set — test_seed_event must run first"
    guid = _STATE["event_guid"]

    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/event/{guid}/expenses", wait_until="networkidle")
    page.wait_for_selector("ion-title:has-text('Expenses')", timeout=15_000)
    page.wait_for_timeout(2_000)

    # Idempotency: skip if expenses already exist
    if page.locator("ion-list ion-item").count() > 0:
        return

    # Open the add-expense form
    page.locator(_ADD_BTN).last.click()
    page.wait_for_selector("ion-card-title:has-text('Add Expense')", timeout=10_000)

    # Select currency (single ion-select → ion-alert → CHF)
    _select_ion_option(page, "currency_id", "CHF")

    # Fill amount
    page.locator("ion-input[formcontrolname='amount']").locator("input").fill("25.00")

    # Select affected users (multi ion-select → ion-alert → first user = event creator)
    # We select any option that appears — the creator is always in the list
    page.locator("ion-select[formcontrolname='affected_user_ids']").click()
    page.locator("ion-alert").wait_for(state="visible", timeout=10_000)
    # Click the first available checkbox option
    page.locator("ion-alert button.alert-tappable").first.click()
    page.locator("ion-alert .alert-button-group button").last.click()
    page.locator("ion-alert").wait_for(state="hidden", timeout=10_000)

    # Date is pre-filled to today; fill description
    page.locator("ion-input[formcontrolname='description']").locator("input").fill("Seed expense")

    page.locator("ion-button[type='submit']").first.click()

    # Form closes and expense row appears
    page.wait_for_timeout(2_000)
    expect(page.locator("ion-list ion-item").first).to_be_visible(timeout=10_000)


def test_seed_settlement(page: Page) -> None:
    """Add a draft CHF 10.00 settlement to the seeded event.

    Idempotent: skips if any settlement already exists.
    """
    assert _STATE.get("event_guid"), "event_guid not set — test_seed_event must run first"
    guid = _STATE["event_guid"]

    ionic_login(page, E2E_USER, E2E_PASSWORD)
    page.goto(f"{IONIC_BASE_URL}/event/{guid}/settlements", wait_until="networkidle")
    page.wait_for_selector("ion-title:has-text('Settlements')", timeout=15_000)
    page.wait_for_timeout(2_000)

    # Idempotency: skip if settlements already exist
    if page.locator("ion-list ion-item").count() > 0:
        return

    # Open add form
    page.locator(_ADD_BTN).last.click()
    page.wait_for_selector("ion-card-title:has-text('Add Settlement')", timeout=10_000)

    # Select recipient (first participant in the list)
    page.locator("ion-select[formcontrolname='recipient_id']").click()
    page.locator("ion-alert").wait_for(state="visible", timeout=10_000)
    page.locator("ion-alert button.alert-tappable").first.click()
    page.locator("ion-alert .alert-button-group button").last.click()
    page.locator("ion-alert").wait_for(state="hidden", timeout=10_000)

    # Select currency
    _select_ion_option(page, "currency_id", "CHF")

    # Fill amount
    page.locator("ion-input[formcontrolname='amount']").locator("input").fill("10.00")

    page.locator("ion-button[type='submit']").first.click()

    # Form closes and settlement row appears (as draft)
    page.wait_for_timeout(2_000)
    expect(page.locator("ion-list ion-item").first).to_be_visible(timeout=10_000)
