from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Final

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError, sync_playwright

from app_config import STREAMLIT_APPS

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
MAX_RETRIES: Final[int] = 2
INTER_APP_DELAY: Final[int] = 3
NAVIGATION_TIMEOUT_MS: Final[int] = 45_000
POST_CLICK_TIMEOUT_MS: Final[int] = 120_000
ARTIFACTS_DIR: Final[Path] = Path("artifacts")
SUMMARY_PATH: Final[Path] = ARTIFACTS_DIR / "summary.json"


def load_app_urls() -> list[str]:
    raw = os.getenv("STREAMLIT_APPS_JSON", "").strip()
    if not raw:
        return list(STREAMLIT_APPS)

    loaded = json.loads(raw)
    if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
        raise ValueError("STREAMLIT_APPS_JSON must be a JSON array of URLs")
    return loaded


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


def slugify_app_url(app_url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", app_url).strip("-").lower()


def save_failure_screenshot(page: Page, app_url: str) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    path = ARTIFACTS_DIR / f"{slugify_app_url(app_url)}.png"
    page.screenshot(path=path, full_page=True)
    return path


def wait_for_app_state(page: Page, timeout_ms: int) -> str:
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


def wake_app(page: Page, app_url: str) -> str:
    page.goto(app_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    initial_state = wait_for_app_state(page, NAVIGATION_TIMEOUT_MS)

    if initial_state == "auth_required":
        return "auth_required"
    if initial_state == "ready":
        return "awake"

    print("    Sleeping - clicking wake button...")
    page.get_by_role("button", name=WAKE_BUTTON_PATTERN).first.click()
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except TimeoutError:
        # Streamlit can keep browser activity alive while the app is waking.
        pass

    final_state = wait_for_app_state(page, POST_CLICK_TIMEOUT_MS)
    if final_state == "auth_required":
        return "auth_required"
    if final_state == "ready":
        return "woken"
    if final_state == "sleeping":
        raise RuntimeError("Wake button is still present after waiting for the app to wake")

    raise RuntimeError("App loaded, but no wake button or app shell was detected")


def run_attempt(context: BrowserContext, app_url: str) -> dict[str, str]:
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        page = context.new_page()
        page.set_default_timeout(NAVIGATION_TIMEOUT_MS)
        try:
            if attempt > 1:
                print(f"    Retry {attempt - 1}/{MAX_RETRIES - 1}...")
                time.sleep(5)

            status = wake_app(page, app_url)
            return {"status": status, "detail": ""}
        except Exception as exc:
            last_error = str(exc)
            print(f"    Attempt {attempt} error: {exc}")
            if attempt == MAX_RETRIES:
                screenshot_path = save_failure_screenshot(page, app_url)
                print(f"    Saved failure screenshot to {screenshot_path}")
                return {"status": "error", "detail": last_error}
        finally:
            page.close()
    return {"status": "error", "detail": last_error}


def write_summary(results: dict[str, int], per_app_results: list[dict[str, str]]) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "results": results,
                "apps": per_app_results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    app_urls = load_app_urls()
    total = len(app_urls)
    results = {"awake": 0, "woken": 0, "auth_required": 0, "error": 0}
    per_app_results: list[dict[str, str]] = []

    with sync_playwright() as playwright:
        context, browser, storage_state_path = build_context(playwright)
        try:
            if storage_state_path:
                print(f"Using Playwright storage state from {storage_state_path}")
            else:
                print("No Playwright storage state provided; only public apps can be woken.")

            for index, app_url in enumerate(app_urls, 1):
                print(f"\n[{index}/{total}] {app_url}")
                result = run_attempt(context, app_url)
                status = result["status"]
                results[status] += 1
                per_app_results.append(
                    {
                        "url": app_url,
                        "status": status,
                        "detail": result["detail"],
                    }
                )
                print(f"    -> {status.upper()}")
                if index < total:
                    time.sleep(INTER_APP_DELAY)
        finally:
            context.close()
            browser.close()

    write_summary(results, per_app_results)

    print(f"\n{'=' * 50}")
    print(f"SUMMARY - {total} apps checked")
    print(f"  Already awake : {results['awake']}")
    print(f"  Woken up      : {results['woken']}")
    print(f"  Auth required : {results['auth_required']}")
    print(f"  Errors        : {results['error']}")
    print(f"  Summary file  : {SUMMARY_PATH}")
    print(f"{'=' * 50}")

    if results["error"] > 0 or results["auth_required"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
