# Streamlit App Waker

Wakes Streamlit apps from GitHub Actions using Playwright and a reusable authenticated storage state.

## What this repo does

1. GitHub Actions runs on a schedule or manual dispatch.
2. Headless Chromium opens every URL in the configured Streamlit app list.
3. If Streamlit shows `Yes, get this app back up!`, the script clicks it.
4. Each app is classified as `awake`, `woken`, `auth_required`, or `error`.
5. A JSON summary and any failure screenshots are uploaded as workflow artifacts.

## Files

- `app_config.py`: shared app list and default validation targets
- `main.py`: wakes all configured apps and writes `artifacts/summary.json`
- `capture_storage_state.py`: captures a Playwright login session for reuse
- `validate_storage_state.py`: checks whether a saved storage state still works
- `.github/workflows/wake.yml`: scheduled GitHub Actions workflow

## Setup

1. Push these files to your GitHub repo.
2. Generate a fresh storage state locally.
3. Validate the storage state against representative apps.
4. Copy the JSON contents into the repository secret `PLAYWRIGHT_STORAGE_STATE_JSON`.
5. Run the workflow from the Actions tab.

## Generate storage state

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 capture_storage_state.py
```

## Validate storage state before uploading

```bash
python3 validate_storage_state.py --storage-state playwright-storage-state.json
```

If validation reports `auth_required`, the saved session is no longer good enough for Actions and should be re-captured before updating the secret.

## Workflow behavior

- The workflow installs Python dependencies and Chromium.
- If `PLAYWRIGHT_STORAGE_STATE_JSON` is present, it materializes and validates the JSON before the wake run starts.
- The run uploads `artifacts/summary.json` and any screenshots even when the wake step fails.
- Workflow concurrency is enabled so a stale older run does not pile up behind a newer one on the same branch.
