from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from app_config import DEFAULT_CAPTURE_URL, DEFAULT_VALIDATE_URLS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a Playwright storage state for Streamlit authentication reuse."
    )
    parser.add_argument(
        "--app-url",
        default=DEFAULT_CAPTURE_URL,
        help="App URL to open while signing in.",
    )
    parser.add_argument(
        "--output",
        default="playwright-storage-state.json",
        help="Path to write the Playwright storage state JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Opening {args.app_url}")
        print("Sign in to Streamlit in the opened browser window if prompted.")
        print("After the app page finishes loading, return here and press Enter.")

        page.goto(args.app_url, wait_until="domcontentloaded", timeout=60_000)
        input()

        context.storage_state(path=str(output_path))
        context.close()
        browser.close()

    print(f"Saved storage state to {output_path.resolve()}")
    print("Validate it before uploading:")
    joined_urls = " ".join(f"--url {url}" for url in DEFAULT_VALIDATE_URLS)
    print(f"python3 validate_storage_state.py --storage-state {output_path} {joined_urls}")
    print("Then copy the file contents into the GitHub secret PLAYWRIGHT_STORAGE_STATE_JSON")


if __name__ == "__main__":
    main()
