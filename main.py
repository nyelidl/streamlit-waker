from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Final

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError, sync_playwright

STREAMLIT_APPS = [
    "https://anyone-docking-01.streamlit.app/",
    "https://anyone-docking-02.streamlit.app/",
    "https://anyone-docking-03.streamlit.app/",
    "https://anyone-docking-04.streamlit.app/",
    "https://anyone-docking-05.streamlit.app/",
    "https://anyone-docking-06.streamlit.app/",
    "https://anyone-docking-07.streamlit.app/",
    "https://anyone-docking-08.streamlit.app/",
    "https://anyone-docking-09.streamlit.app/",
    "https://anyone-docking-10.streamlit.app/",
    "https://anyone-docking-11.streamlit.app/",
    "https://anyone-docking-12.streamlit.app/",
    "https://anyone-docking-13.streamlit.app/",
    "https://anyone-docking-14.streamlit.app/",
    "https://anyone-docking-15.streamlit.app/",
    "https://anyone-docking-16.streamlit.app/",
    "https://anyone-docking-17.streamlit.app/",
    "https://anyone-docking-18.streamlit.app/",
    "https://anyone-docking-19.streamlit.app/",
    "https://anyone-docking-20.streamlit.app/",
    "https://anyone-docking-21.streamlit.app/",
    "https://anyone-docking-22.streamlit.app/",
    "https://anyone-docking-23.streamlit.app/",
    "https://anyone-docking-24.streamlit.app/",
    "https://anyone-docking.streamlit.app/",
    "https://pkanetcloud.streamlit.app/",
    "https://ligandbuilder.streamlit.app/",
]

WAKE_BUTTON_PATTERN: Final[re.Pattern[str]] = re.compile(r"get this app back up", re.IGNORECASE)
AUTH_URL_MARKERS: Final[tuple[str, ...]] = ("share.streamlit.io/-/auth", "/-/login")
APP_READY_SELECTORS: Final[tuple[str, ...]] = (
    "div[data-testid='stAppViewContainer']",
    "[data-testid='stSidebar']",
    "section.main",
)
MAX_RETRIES: Final[int] = 2
INTER_APP_DELAY: Final[int] = 3
NAVIGATION_TIMEOUT_MS: Final[int] = 45_000
POST_CLICK_TIMEOUT_MS: Final[int] = 120_000
ARTIFACTS_DIR: Final[Path] = Path("artifacts")


def build_context(playwright) -> tuple[BrowserContext, Browser, str | None]:
    browser = playwright.chromium.launch(headless=True)
    storage_state_path = os.getenv("PLAYWRIGHT_STORAGE_STATE_PATH")

    if storage_state_path:
        context = browser.new_context(storage_state=storage_state_path)
        return context, browser, storage_state_path

    context = browser.new_context()
    return context, browser, None


def is_auth_redirect(page: Page) -> bool:
    current_url = page.url.lower()
    return any(marker in current_url for marker in AUTH_URL_MARKERS)


def page_has_wake_button(page: Page) -> bool:
    return page.get_by_role("button", name=WAKE_BUTTON_PATTERN).count() > 0


def page_looks_ready(page: Page) -> bool:
    for selector in APP_READY_SELECTORS:
        if page.locator(selector).count() > 0:
            return True
    return False


def save_failure_screenshot(page: Page, app_url: str) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", app_url).strip("-").lower()
    path = ARTIFACTS_DIR / f"{slug}.png"
    page.screenshot(path=path, full_page=True)
    return path


def wait_for_awake_or_sleep(page: Page) -> None:
    deadline = time.time() + (NAVIGATION_TIMEOUT_MS / 1000)
    while time.time() < deadline:
        if is_auth_redirect(page) or page_has_wake_button(page) or page_looks_ready(page):
            return
        time.sleep(1)
    raise TimeoutError("Timed out waiting for Streamlit app state")


def wake_app(page: Page, app_url: str) -> str:
    page.goto(app_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    wait_for_awake_or_sleep(page)

    if is_auth_redirect(page):
        return "auth_required"

    wake_button = page.get_by_role("button", name=WAKE_BUTTON_PATTERN)
    if wake_button.count() > 0:
        print("    Sleeping - clicking wake button...")
        wake_button.first.click()
        page.wait_for_load_state("networkidle", timeout=POST_CLICK_TIMEOUT_MS)
        wait_for_awake_or_sleep(page)
        if is_auth_redirect(page):
            return "auth_required"
        return "woken"

    if page_looks_ready(page):
        return "awake"

    raise RuntimeError("App loaded, but no wake button or app shell was detected")


def run_attempt(page: Page, app_url: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                print(f"    Retry {attempt - 1}/{MAX_RETRIES - 1}...")
                time.sleep(5)
            return wake_app(page, app_url)
        except Exception as exc:
            print(f"    Attempt {attempt} error: {exc}")
            if attempt == MAX_RETRIES:
                screenshot_path = save_failure_screenshot(page, app_url)
                print(f"    Saved failure screenshot to {screenshot_path}")
                return "error"
    return "error"


def main() -> None:
    total = len(STREAMLIT_APPS)
    results = {"awake": 0, "woken": 0, "auth_required": 0, "error": 0}

    with sync_playwright() as playwright:
        context, browser, storage_state_path = build_context(playwright)
        try:
            page = context.new_page()
            page.set_default_timeout(NAVIGATION_TIMEOUT_MS)

            if storage_state_path:
                print(f"Using Playwright storage state from {storage_state_path}")
            else:
                print("No Playwright storage state provided; only public apps can be woken.")

            for i, app_url in enumerate(STREAMLIT_APPS, 1):
                print(f"\n[{i}/{total}] {app_url}")
                status = run_attempt(page, app_url)
                results[status] += 1
                print(f"    -> {status.upper()}")
                if i < total:
                    time.sleep(INTER_APP_DELAY)
        finally:
            context.close()
            browser.close()

    print(f"\n{'=' * 50}")
    print(f"SUMMARY - {total} apps checked")
    print(f"  Already awake : {results['awake']}")
    print(f"  Woken up      : {results['woken']}")
    print(f"  Auth required : {results['auth_required']}")
    print(f"  Errors        : {results['error']}")
    print(f"{'=' * 50}")

    if results["error"] > 0 or results["auth_required"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
