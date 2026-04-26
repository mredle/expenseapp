# coding=utf-8
"""Shared Playwright fixtures for E2E tests covering the Ionic app and Flask HTML routes."""

from __future__ import annotations

import os
import tempfile
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

# ---------------------------------------------------------------------------
# URLs — override via environment variables when running against a live server
# ---------------------------------------------------------------------------
IONIC_BASE_URL: str = os.environ.get("E2E_IONIC_URL", "http://localhost:4200")
FLASK_BASE_URL: str = os.environ.get("E2E_FLASK_URL", "http://localhost:5000")

# Default credentials — match the accounts created by bootstrap_Flask_DEBUG.sh:
#   flask dbinit admin   → username: admin,  password: pw
#   flask dbinit dummyusers --count 3 → User0/User0, User1/User1, User2/User2
E2E_USER: str = os.environ.get("E2E_USER", "User0")
E2E_PASSWORD: str = os.environ.get("E2E_PASSWORD", "User0")
E2E_ADMIN: str = os.environ.get("E2E_ADMIN", "admin")
E2E_ADMIN_PASSWORD: str = os.environ.get("E2E_ADMIN_PASSWORD", "pw")


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
    """Launch a headless Chromium browser shared across the entire test session."""
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
# Session-scoped authenticated storage states
#
# These fixtures perform a single real login per session and save the browser
# storage state (cookies + localStorage) to a temp file.  Per-test fixtures
# restore that state into a fresh context so tests start already authenticated
# without hitting the Flask rate limiter on every test.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _pre_warm_flask_storage_states(
    flask_user_storage_state: str, flask_admin_storage_state: str
) -> None:
    """Force Flask storage states to be created before any test runs.

    This autouse fixture ensures both login sessions are established at the
    very start of the test run, consuming only 2 requests against the Flask
    rate limiter (12/min) before the auth tests begin.
    """


@pytest.fixture(scope="session")
def flask_user_storage_state(browser: Browser) -> Generator[str, None, None]:
    """Log in once as the regular user and persist the storage state to a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        state_path = f.name

    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    page = ctx.new_page()
    _do_flask_login(page, E2E_USER, E2E_PASSWORD)
    ctx.storage_state(path=state_path)
    page.close()
    ctx.close()
    yield state_path
    os.unlink(state_path)


@pytest.fixture(scope="session")
def flask_admin_storage_state(browser: Browser) -> Generator[str, None, None]:
    """Log in once as the admin user and persist the storage state to a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        state_path = f.name

    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    page = ctx.new_page()
    _do_flask_login(page, E2E_ADMIN, E2E_ADMIN_PASSWORD)
    ctx.storage_state(path=state_path)
    page.close()
    ctx.close()
    yield state_path
    os.unlink(state_path)


@pytest.fixture
def flask_user_page(browser: Browser, flask_user_storage_state: str) -> Generator[Page, None, None]:
    """Yield a Page that is already authenticated as the regular Flask user.

    Uses the pre-saved storage state so no new login request is made, avoiding
    the rate limiter on the /auth/authenticate_password endpoint.
    """
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
        storage_state=flask_user_storage_state,
    )
    p = ctx.new_page()
    yield p
    p.close()
    ctx.close()


@pytest.fixture
def flask_admin_page(browser: Browser, flask_admin_storage_state: str) -> Generator[Page, None, None]:
    """Yield a Page that is already authenticated as the admin Flask user.

    Uses the pre-saved storage state so no new login request is made, avoiding
    the rate limiter on the /auth/authenticate_password endpoint.
    """
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
        storage_state=flask_admin_storage_state,
    )
    p = ctx.new_page()
    yield p
    p.close()
    ctx.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _do_flask_login(page: Page, username: str, password: str) -> None:
    """Internal: perform a real Flask login.  Used only by the storage-state fixtures."""
    # Retry up to 5 times with exponential back-off to handle the rate limiter
    # (12 req/min on GET+POST for /auth/authenticate_password).
    import time
    for attempt in range(5):
        if attempt > 0:
            time.sleep(5 * attempt)  # 5s, 10s, 15s, 20s back-off
        page.goto(
            f"{FLASK_BASE_URL}/auth/authenticate_password",
            wait_until="networkidle",
            timeout=20_000,
        )
        if page.locator("input[name='username']").count() > 0:
            break
    page.locator("input[name='username']").wait_for(state="visible", timeout=10_000)
    page.locator("input[name='username']").fill(username)
    page.locator("input[name='password']").fill(password)
    page.locator("input[name='submit']").click()
    page.wait_for_load_state("networkidle", timeout=15_000)


def flask_login(
    page: Page, username: str = E2E_USER, password: str = E2E_PASSWORD
) -> None:
    """Log in via the Flask HTML login form.

    Prefer using the ``flask_user_page`` / ``flask_admin_page`` fixtures instead
    of calling this function directly.  Those fixtures reuse a session-scoped
    storage state and avoid triggering the rate limiter on
    /auth/authenticate_password.  Call this function only when you explicitly
    need to test the login form itself (e.g. ``test_flask_auth.py``).
    """
    _do_flask_login(page, username, password)


def ionic_login(page: Page, username: str = E2E_USER, password: str = E2E_PASSWORD) -> None:
    """Navigate to the Ionic login page and authenticate with username/password.

    Ionic uses client-side routing (Angular Router) so no browser navigation
    event fires on login success. We fill the shadow-DOM inner <input> elements
    directly and poll page.url until the route changes away from /auth/login.
    """
    page.goto(f"{IONIC_BASE_URL}/auth/login", wait_until="networkidle", timeout=20_000)
    # ion-input uses shadow DOM — target the inner <input> directly
    page.locator("ion-input[formcontrolname='username']").locator("input").fill(username)
    page.locator("ion-input[formcontrolname='password']").locator("input").fill(password)
    page.locator("ion-button[type='submit']").click()
    # Poll until the Angular router navigates away from /auth/login
    page.wait_for_url(f"{IONIC_BASE_URL}/tabs/**", timeout=15_000)
