from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Final

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError, sync_playwright

from app_config import DEFAULT_VALIDATE_URLS

WAKE_BUTTON_PATTERN: Final[re.Pattern[str]] = re.compile(r"get this app back up", re.IGNORECASE)
AUTH_URL_MARKERS: Final[tuple[str, ...]] = ("share.streamlit.io/-/auth", "/-/login")
AUTH_TEXT_MARKERS: Final[tuple[str, ...]] = (
    "sign in with streamlit",
    "continue with google",
    "continue with email",
    "log in to continue",
)
APP_READY_SELECTORS: Final[tuple[str, ...]] = (
    "div[data-testid='stAppViewContainer']",
    "[data-testid='stSidebar']",
    "section.main",
)
NAVIGATION_TIMEOUT_MS: Final[int] = 45_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that a Playwright storage state can still access Streamlit apps."
    )
    parser.add_argument(
        "--storage-state",
        default="playwright-storage-state.json",
        help="Path to the Playwright storage state JSON file.",
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="App URL to validate. Repeat to validate multiple apps.",
    )
    return parser.parse_args()


def is_auth_redirect(page: Page) -> bool:
    current_url = page.url.lower()
    return any(marker in current_url for marker in AUTH_URL_MARKERS)


def page_text(page: Page) -> str:
    try:
        return (page.locator("body").inner_text(timeout=2_000) or "").lower()
    except Exception:
        return ""


def page_has_auth_prompt(page: Page) -> bool:
    return any(marker in page_text(page) for marker in AUTH_TEXT_MARKERS)


def page_has_wake_button(page: Page) -> bool:
    return page.get_by_role("button", name=WAKE_BUTTON_PATTERN).count() > 0


def page_looks_ready(page: Page) -> bool:
    return any(page.locator(selector).count() > 0 for selector in APP_READY_SELECTORS)


def wait_for_state(page: Page, timeout_ms: int) -> str:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if is_auth_redirect(page) or page_has_auth_prompt(page):
            return "auth_required"
        if page_has_wake_button(page):
            return "sleeping"
        if page_looks_ready(page):
            return "ready"
        time.sleep(1)
    raise TimeoutError("Timed out waiting for Streamlit app state")


def build_context(playwright, storage_state_path: Path) -> tuple[BrowserContext, Browser]:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(storage_state_path))
    return context, browser


def validate_url(context: BrowserContext, url: str) -> str:
    page = context.new_page()
    page.set_default_timeout(NAVIGATION_TIMEOUT_MS)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        return wait_for_state(page, NAVIGATION_TIMEOUT_MS)
    finally:
        page.close()


def main() -> None:
    args = parse_args()
    storage_state_path = Path(args.storage_state)
    urls = args.urls or list(DEFAULT_VALIDATE_URLS)

    if not storage_state_path.exists():
        raise SystemExit(f"Storage state file not found: {storage_state_path}")

    failures = 0
    with sync_playwright() as playwright:
        context, browser = build_context(playwright, storage_state_path)
        try:
            for url in urls:
                result = validate_url(context, url)
                print(f"{url} -> {result}")
                if result == "auth_required":
                    failures += 1
        finally:
            context.close()
            browser.close()

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
