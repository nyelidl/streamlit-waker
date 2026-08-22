from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Final, Union

from playwright.sync_api import Browser, BrowserContext, Frame, Page, TimeoutError, sync_playwright

from app_config import DEFAULT_VALIDATE_URLS

WAKE_BUTTON_PATTERN: Final[re.Pattern[str]] = re.compile(r"get this app back up", re.IGNORECASE)
AUTH_URL_MARKERS: Final[tuple[str, ...]] = ("share.streamlit.io/-/auth", "/-/login")
AUTH_TEXT_MARKERS: Final[tuple[str, ...]] = (
    "sign in with streamlit",
    "continue with google",
    "continue with email",
    "log in to continue",
)
WAKE_TEXT_MARKERS: Final[tuple[str, ...]] = (
    "yes, get this app back up",
    "get this app back up",
    "this app has gone to sleep",
)
APP_READY_SELECTORS: Final[tuple[str, ...]] = (
    "div[data-testid='stAppViewContainer']",
    "[data-testid='stSidebar']",
    "[data-testid='stHeader']",
    "div.stApp",
    "section.main",
)
NAVIGATION_TIMEOUT_MS: Final[int] = 45_000
DEBUG_DIR: Final[Path] = Path("artifacts") / "validation-debug"
StreamlitScope = Union[Page, Frame]


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


def get_scopes(page: Page) -> list[StreamlitScope]:
    scopes: list[StreamlitScope] = [page]
    scopes.extend(frame for frame in page.frames if frame != page.main_frame)
    return scopes


def is_auth_redirect(page: Page) -> bool:
    frame_urls = [page.url.lower(), *(frame.url.lower() for frame in page.frames)]
    return any(marker in url for marker in AUTH_URL_MARKERS for url in frame_urls)


def scope_text(scope: StreamlitScope) -> str:
    try:
        text = scope.locator("body").inner_text(timeout=2_000) or ""
        if text.strip():
            return text.lower()
    except Exception:
        pass
    try:
        return (scope.locator("body").text_content(timeout=2_000) or "").lower()
    except Exception:
        return ""


def page_has_auth_prompt(page: Page) -> bool:
    return any(any(marker in scope_text(scope) for marker in AUTH_TEXT_MARKERS) for scope in get_scopes(page))


def page_has_wake_button(page: Page) -> bool:
    return any(scope.get_by_role("button", name=WAKE_BUTTON_PATTERN).count() > 0 for scope in get_scopes(page))


def page_has_wake_text(page: Page) -> bool:
    return any(any(marker in scope_text(scope) for marker in WAKE_TEXT_MARKERS) for scope in get_scopes(page))


def page_looks_ready(page: Page) -> bool:
    fallback_selectors = (
        "div[data-testid='stMarkdownContainer']",
        "[role='tab']",
        "input[type='radio']",
        "input[type='file']",
        "textarea",
    )
    selectors = APP_READY_SELECTORS + fallback_selectors
    return any(any(scope.locator(selector).count() > 0 for selector in selectors) for scope in get_scopes(page))


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()


def write_debug_artifacts(page: Page, url: str) -> dict[str, str]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(url)
    screenshot_path = DEBUG_DIR / f"{slug}.png"
    html_path = DEBUG_DIR / f"{slug}.html"
    meta_path = DEBUG_DIR / f"{slug}.json"

    page.screenshot(path=screenshot_path, full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "url": page.url,
                "title": page.title(),
                "text_excerpt": scope_text(page)[:2000],
                "frame_urls": [frame.url for frame in page.frames],
                "wake_button_detected": page_has_wake_button(page),
                "wake_text_detected": page_has_wake_text(page),
                "auth_prompt_detected": page_has_auth_prompt(page),
                "ready_detected": page_looks_ready(page),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "screenshot": str(screenshot_path),
        "html": str(html_path),
        "meta": str(meta_path),
    }


def wait_for_state(page: Page, timeout_ms: int) -> str:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if is_auth_redirect(page) or page_has_auth_prompt(page):
            return "auth_required"
        if page_has_wake_button(page) or page_has_wake_text(page):
            return "sleeping"
        if page_looks_ready(page):
            return "ready"
        time.sleep(1)
    debug_paths = write_debug_artifacts(page, page.url or "unknown")
    raise TimeoutError(
        "Timed out waiting for Streamlit app state. "
        f"Saved debug artifacts: {debug_paths['screenshot']}, {debug_paths['html']}, {debug_paths['meta']}"
    )


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
