# ⚡ Qwen HTTP Account Maker (GitHub Actions & Local)

Automated, API-driven Qwen account generator with automated Aliyun slider CAPTCHA solving, Mazdoor temporary mail integration, and pure HTTP OTP verification.

Designed to run **100% standalone** both locally and directly via **GitHub Actions**.

---

## 🌟 Key Features
- **GitHub Actions Ready:** Run directly in the cloud on GitHub runners without hosting any server.
- **Pure HTTP Account Flow:** Email creation, OTP polling, and token verification happen via high-speed HTTP requests.
- **Embedded Slider Solver:** Includes an embedded real-page CloakBrowser slider solver with Sobel-x template matching.
- **Artifact Export:** Automatically packages created accounts into downloadable GitHub Actions artifacts (`accounts.json` & `accounts.txt`).
- **Resilient Retry:** Auto-retries with fresh inboxes if email delivery or challenge encounters transient latency.

---

## 📁 Repository Structure
```text
qwen-http-maker/
├── .github/
│   └── workflows/
│       └── create_accounts.yml   # GitHub Actions workflow (dispatch & runner)
├── solver/
│   ├── __init__.py
│   ├── realpage.py               # Aliyun real-page slider automation engine
│   ├── gap_cv.py                 # Pure Sobel-x gradient gap detector
│   └── browser_helpers.py        # Playwright/CDP action helpers
├── main.py                       # Main CLI entrypoint (Single & batch mode)
├── mazdoor.py                    # Mazdoor Temporary Mail API client
├── config.py                     # Central configuration & endpoints
├── requirements.txt              # Minimal Python dependencies
├── run.sh                        # Local 1-click execution script
├── .gitignore                    # Keeps credentials & cache safe
└── README.md                     # Documentation
```

---

## 🚀 How to Run on GitHub Actions

1. **Push this repository to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Qwen HTTP Account Maker"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/<REPO_NAME>.git
   git push -u origin main
   ```

2. **Run the Workflow:**
   - Go to your repository on GitHub.
   - Click on the **Actions** tab.
   - Select **Create Qwen Accounts** from the left sidebar.
   - Click the **Run workflow** dropdown button.
   - Enter how many accounts to create (e.g. `3` or `5`) and click **Run workflow**.

3. **Download Accounts:**
   - Once the action run finishes, click on the completed run.
   - Scroll down to the **Artifacts** section at the bottom of the summary page.
   - Click to download **`qwen-accounts-<run_id>`** (contains `accounts.json` and `accounts.txt`).

---

## 💻 How to Run Locally

### Requirements
- Python 3.10+
- macOS or Linux

### Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m cloakbrowser install

# 2. Run Single Account Creation
./run.sh

# 3. Run Batch Mode (e.g. 5 accounts)
./run.sh --count 5 --delay 5
```

---

## 💾 Output Formats

All generated credentials are saved into `output/`:

### `output/accounts.json`
```json
[
  {
    "email": "user@mazdoor.me",
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "authorization": "Bearer eyJhbGci...",
    "cookies": { ... },
    "status": "success",
    "created_at": "2026-10-16 12:00:00"
  }
]
```

### `output/accounts.txt`
```text
user@mazdoor.me:eyJhbGciOiJIUzI1NiIs...
```

---

## 🛡️ Privacy & Safety
The repository is pre-configured with a strict `.gitignore` that prevents any created accounts or tokens in `output/*.json` and `output/*.txt` from ever being committed to GitHub.
