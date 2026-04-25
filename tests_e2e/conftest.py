# coding=utf-8
"""Shared Playwright fixtures for E2E tests covering the Ionic app and Flask HTML routes."""

from __future__ import annotations

import os
import threading
import time
from typing import Generator

import pytest
from flask import Flask
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

# ---------------------------------------------------------------------------
# URLs — override via environment variables when running against a live server
# ---------------------------------------------------------------------------
IONIC_BASE_URL: str = os.environ.get("E2E_IONIC_URL", "http://localhost:4200")
FLASK_BASE_URL: str = os.environ.get("E2E_FLASK_URL", "http://localhost:5000")

# Default credentials used across all tests (must exist in the running DB)
E2E_USER: str = os.environ.get("E2E_USER", "e2euser")
E2E_PASSWORD: str = os.environ.get("E2E_PASSWORD", "e2epassword")
E2E_ADMIN: str = os.environ.get("E2E_ADMIN", "e2eadmin")
E2E_ADMIN_PASSWORD: str = os.environ.get("E2E_ADMIN_PASSWORD", "e2eadminpassword")


# ---------------------------------------------------------------------------
# Playwright browser / context / page fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    """Start a single Playwright session for the whole test run."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Generator[Browser, None, None]:
    """Launch a headless Chromium browser shared across all tests in a session."""
    headless = os.environ.get("E2E_HEADLESS", "1") != "0"
    b = playwright_instance.chromium.launch(headless=headless)
    yield b
    b.close()


@pytest.fixture
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Create a fresh browser context (isolated cookies/storage) per test."""
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},  # iPhone 14 viewport
        ignore_https_errors=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Open a new page inside the per-test context."""
    p = context.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ionic_login(page: Page, username: str = E2E_USER, password: str = E2E_PASSWORD) -> None:
    """Navigate to the Ionic login page and authenticate with username/password."""
    page.goto(f"{IONIC_BASE_URL}/auth/login")
    page.wait_for_selector("ion-input[formcontrolname='username']", timeout=15_000)
    page.locator("ion-input[formcontrolname='username']").click()
    page.keyboard.type(username)
    page.locator("ion-input[formcontrolname='password']").click()
    page.keyboard.type(password)
    page.locator("ion-button[type='submit']").click()
    # Wait until redirected away from login
    page.wait_for_url(lambda url: "/auth/login" not in url, timeout=15_000)


def flask_login(
    page: Page, username: str = E2E_USER, password: str = E2E_PASSWORD
) -> None:
    """Log in via the Flask HTML login form."""
    page.goto(f"{FLASK_BASE_URL}/auth/authenticate_password")
    page.wait_for_selector("input[name='username']", timeout=15_000)
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.locator("input[type='submit'], button[type='submit']").first.click()
    page.wait_for_url(lambda url: "/auth/authenticate_password" not in url, timeout=15_000)
