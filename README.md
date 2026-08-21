# Streamlit App Waker

Wakes Streamlit apps from GitHub Actions using Playwright.

## How it works

1. GitHub Actions runs on a schedule
2. Playwright opens each app URL in headless Chromium
3. If Streamlit shows `Yes, get this app back up!`, the script clicks it
4. The workflow logs which apps were already awake, woken, auth-blocked, or errored

## Setup

1. Push these files to your GitHub repo
2. Add the secret `PLAYWRIGHT_STORAGE_STATE_JSON`
3. Run the workflow from the Actions tab

## Generate storage state

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 capture_storage_state.py
