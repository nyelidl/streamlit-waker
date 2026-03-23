from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
import time

# ═══════════════════════════════════════════════════════════════
#  All 10 "Anyone Can Dock" instances
# ═══════════════════════════════════════════════════════════════
STREAMLIT_APPS = [
    "https://anyone-docking.streamlit.app/",
    "https://anyone-docking-2.streamlit.app/",
    "https://anyone-docking-3.streamlit.app/",
    "https://anyone-docking-4.streamlit.app/",
    "https://anyone-docking-5.streamlit.app/",
    "https://anyone-docking-6.streamlit.app/",
    "https://anyone-docking-7.streamlit.app/",
    "https://anyone-docking-8.streamlit.app/",
    "https://anyone-docking-9.streamlit.app/",
    "https://anyone-docking-10.streamlit.app/",
]


def wake_app(driver, url):
    """Visit a single Streamlit app and click the wake button if present."""
    try:
        driver.get(url)
        print(f"\n{'─'*50}")
        print(f"🔗 Visiting: {url}")

        wait = WebDriverWait(driver, 20)
        try:
            button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(),'Yes, get this app back up')]")
                )
            )
            print("💤 App was sleeping — clicking wake button...")
            button.click()

            try:
                wait.until(
                    EC.invisibility_of_element_located(
                        (By.XPATH, "//button[contains(text(),'Yes, get this app back up')]")
                    )
                )
                print(f"✅ Woken up successfully: {url}")
                return "woken"
            except TimeoutException:
                print(f"⚠️  Button clicked but didn't disappear: {url}")
                return "uncertain"

        except TimeoutException:
            print(f"✅ Already awake: {url}")
            return "awake"

    except Exception as e:
        print(f"❌ Error for {url}: {e}")
        return "error"


def main():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    results = {"awake": 0, "woken": 0, "uncertain": 0, "error": 0}

    try:
        for i, url in enumerate(STREAMLIT_APPS, 1):
            print(f"\n[{i}/{len(STREAMLIT_APPS)}]", end="")
            status = wake_app(driver, url)
            results[status] += 1
            # Small delay between apps to avoid rate-limiting
            if i < len(STREAMLIT_APPS):
                time.sleep(3)
    finally:
        driver.quit()

    # ── Summary ───────────────────────────────────────────────
    print(f"\n{'═'*50}")
    print(f"📊 SUMMARY — {len(STREAMLIT_APPS)} apps checked")
    print(f"   ✅ Already awake: {results['awake']}")
    print(f"   🔔 Woken up:     {results['woken']}")
    print(f"   ⚠️  Uncertain:    {results['uncertain']}")
    print(f"   ❌ Errors:       {results['error']}")
    print(f"{'═'*50}")

    if results["error"] > 0:
        print("⚠️  Some apps had errors — check logs above.")
        exit(1)
    else:
        print("🎉 All apps are awake!")


if __name__ == "__main__":
    main()
