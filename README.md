# ☕ Streamlit App Waker — Anyone Can Dock

Keeps all 10 **Anyone Can Dock** Streamlit instances awake using **Selenium + GitHub Actions**.

## How it works

1. A GitHub Actions cron job runs every **4 hours**
2. Selenium (headless Chrome) visits each of the 10 app URLs
3. If the app is sleeping, it clicks **"Yes, get this app back up!"**
4. Logs a summary of which apps were awake vs woken up


## Setup

1. Create a new GitHub repo
2. Copy these files into it (preserving the `.github/workflows/` folder)
3. Push to GitHub
4. Go to **Actions** tab → **Wake All Streamlit Apps** → **Run workflow** to test

## Customise

- **Schedule**: edit `cron` in `.github/workflows/wake.yml`  
  - `"0 */4 * * *"` = every 4 hours  
  - `"0 */2 * * *"` = every 2 hours  
  - `"0 */6 * * *"` = every 6 hours  
- **Add/remove apps**: edit the `STREAMLIT_APPS` list in `main.py`
