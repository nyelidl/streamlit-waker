from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

APP_URL = "https://anyone-docking.streamlit.app/"
OUTPUT_PATH = Path("playwright-storage-state.json")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Opening {APP_URL}")
        print("Sign in to Streamlit in the opened browser window if prompted.")
        print("After the app page finishes loading, return here and press Enter.")

        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
        input()

        context.storage_state(path=str(OUTPUT_PATH))
        context.close()
        browser.close()

    print(f"Saved storage state to {OUTPUT_PATH.resolve()}")
    print("Copy the file contents into the GitHub secret PLAYWRIGHT_STORAGE_STATE_JSON")


if __name__ == "__main__":
    main()
