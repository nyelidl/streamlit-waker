from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
import time

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

WAKE_XPATH = "//button[contains(., 'get this app back up')]"
APP_READY_XPATH = (
    "//*[contains(., 'Anyone Can Dock') or contains(., 'anyone can dock')]"
)

def wait_for_document_ready(driver, timeout=30):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

def wake_app(driver, url):
    try:
        print(f"\n{'─'*50}")
        print(f"🔗 Visiting: {url}")
        driver.get(url)
        wait_for_document_ready(driver, timeout=30)

        wait = WebDriverWait(driver, 20)

        # Case 1: sleeping app
        try:
            button = wait.until(
                EC.element_to_be_clickable((By.XPATH, WAKE_XPATH))
            )
            print("💤 App was sleeping — clicking wake button...")
            button.click()

            # After clicking, wait for either app content or button disappearance
            try:
                WebDriverWait(driver, 60).until(
                    lambda d: (
                        len(d.find_elements(By.XPATH, APP_READY_XPATH)) > 0 or
                        len(d.find_elements(By.XPATH, WAKE_XPATH)) == 0
                    )
                )

                if driver.find_elements(By.XPATH, APP_READY_XPATH):
                    print(f"✅ Woken up successfully: {url}")
                    return "woken"
                else:
                    print(f"⚠️ Wake button disappeared, but app content not confirmed: {url}")
                    return "uncertain"

            except TimeoutException:
                print(f"⚠️ Timed out waiting for app after wake click: {url}")
                return "uncertain"

        except TimeoutException:
            pass

        # Case 2: already awake
        if driver.find_elements(By.XPATH, APP_READY_XPATH):
            print(f"✅ Already awake: {url}")
            return "awake"

        # Case 3: neither sleeping button nor app content found
        print(f"⚠️ No wake button and app content not detected: {url}")
        return "uncertain"

    except Exception as e:
        print(f"❌ Error for {url}: {e}")
        return "error"

def main():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

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
            if i < len(STREAMLIT_APPS):
                time.sleep(3)
    finally:
        driver.quit()

    print(f"\n{'═'*50}")
    print(f"📊 SUMMARY — {len(STREAMLIT_APPS)} apps checked")
    print(f"   ✅ Already awake: {results['awake']}")
    print(f"   🔔 Woken up:     {results['woken']}")
    print(f"   ⚠️ Uncertain:    {results['uncertain']}")
    print(f"   ❌ Errors:       {results['error']}")
    print(f"{'═'*50}")

    if results["error"] > 0 or results["uncertain"] > 0:
        print("⚠️ Some apps need manual checking.")
        raise SystemExit(1)
    else:
        print("🎉 All apps are awake!")

if __name__ == "__main__":
    main()
