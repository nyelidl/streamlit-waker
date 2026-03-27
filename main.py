from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
import time

# ── App list (must match index.html exactly) ──────────────────────────────────
STREAMLIT_APPS = [
    "https://anyone-docking-0.streamlit.app/",
    "https://anyone-docking-1.streamlit.app/",
    "https://anyone-docking-2.streamlit.app/",
    "https://anyone-docking-3.streamlit.app/",
    "https://anyone-docking-4.streamlit.app/",
    "https://anyone-docking-5.streamlit.app/",
    "https://anyone-docking-6.streamlit.app/",
    "https://anyone-docking-7.streamlit.app/",
    "https://anyone-docking-8.streamlit.app/",
    "https://anyone-docking-9.streamlit.app/",
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
]

WAKE_XPATH      = "//button[contains(., 'get this app back up')]"
APP_READY_XPATH = "//*[contains(., 'Anyone Can Dock') or contains(., 'anyone can dock')]"
MAX_RETRIES     = 2   # retry once on uncertain/error before giving up
INTER_APP_DELAY = 3   # seconds between apps


# ── Helpers ───────────────────────────────────────────────────────────────────

def wait_for_document_ready(driver, timeout: int = 30) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def _try_wake(driver, url: str) -> str:
    """Single attempt to wake one app. Returns: awake | woken | uncertain | error."""
    driver.get(url)
    wait_for_document_ready(driver, timeout=30)
    wait = WebDriverWait(driver, 20)

    # Case 1: app is sleeping — click the wake button
    try:
        button = wait.until(EC.element_to_be_clickable((By.XPATH, WAKE_XPATH)))
        print("    💤 Sleeping — clicking wake button…")
        button.click()

        try:
            WebDriverWait(driver, 60).until(
                lambda d: (
                    bool(d.find_elements(By.XPATH, APP_READY_XPATH)) or
                    not d.find_elements(By.XPATH, WAKE_XPATH)
                )
            )
            if driver.find_elements(By.XPATH, APP_READY_XPATH):
                return "woken"
            return "uncertain"
        except TimeoutException:
            return "uncertain"

    except TimeoutException:
        pass  # button not found — app may already be awake

    # Case 2: already awake
    if driver.find_elements(By.XPATH, APP_READY_XPATH):
        return "awake"

    # Case 3: indeterminate state
    return "uncertain"


def wake_app(driver, url: str) -> str:
    """Attempt to wake an app, retrying on uncertain/error outcomes."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                print(f"    🔄 Retry {attempt - 1}/{MAX_RETRIES - 1}…")
                time.sleep(5)

            status = _try_wake(driver, url)

            if status in ("awake", "woken"):
                return status

            print(f"    ⚠️  Attempt {attempt} uncertain — {'retrying' if attempt < MAX_RETRIES else 'giving up'}.")

        except Exception as exc:
            print(f"    ❌ Attempt {attempt} raised: {exc}")
            if attempt == MAX_RETRIES:
                return "error"

    return "uncertain"


# ── Driver setup ──────────────────────────────────────────────────────────────

def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    total   = len(STREAMLIT_APPS)
    results = {"awake": 0, "woken": 0, "uncertain": 0, "error": 0}

    driver = build_driver()
    try:
        for i, url in enumerate(STREAMLIT_APPS, 1):
            print(f"\n[{i}/{total}] {url}")
            status = wake_app(driver, url)
            results[status] += 1

            icons = {"awake": "✅", "woken": "🔔", "uncertain": "⚠️", "error": "❌"}
            print(f"    → {icons[status]} {status.upper()}")

            if i < total:
                time.sleep(INTER_APP_DELAY)
    finally:
        driver.quit()

    # Summary
    print(f"\n{'═' * 50}")
    print(f"📊 SUMMARY — {total} apps checked")
    print(f"   ✅ Already awake : {results['awake']}")
    print(f"   🔔 Woken up      : {results['woken']}")
    print(f"   ⚠️  Uncertain     : {results['uncertain']}")
    print(f"   ❌ Errors        : {results['error']}")
    print(f"{'═' * 50}")

    if results["error"] > 0 or results["uncertain"] > 0:
        print("⚠️  Some apps need manual checking.")
        raise SystemExit(1)

    print("🎉 All apps are awake!")


if __name__ == "__main__":
    main()
