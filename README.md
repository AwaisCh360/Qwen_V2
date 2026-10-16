# ⚡ Qwen HTTP Account Maker (V2)

High-speed, automated Qwen account maker powered by Mazdoor Temporary Mail API, YOLOv8n ONNX gap detector, and natural ballistic kinematic puzzle slider solver.

Runs **100% standalone** both locally and directly via **GitHub Actions** with automated Git persistence.

---

## 🌟 Key Features

- **Embedded YOLOv8n ONNX Gap Detector**: Ultra-fast (15–30ms) CPU neural network inference (`best.onnx`) with thread optimization.
- **Natural Human Kinematic Solver**:
  - Realistic human reaction delay (`1.2s – 1.8s`) before touching puzzle.
  - Organic screen-to-slider approach movement (eliminates teleportation bot flags).
  - Proper Chrome DevTools Protocol pointer button states (`buttons: 1`).
  - Track boundary clamping (`max_track: 254.0px`) preventing right-wall collisions.
  - Ballistic cubic ease-out overshoot with smooth reverse drift.
- **Pure HTTP OTP Flow**: Fast polling via Mazdoor temporary email API with direct HTTP activation.
- **Auto-Commit & Artifact Sync**: GitHub Actions workflow automatically persists newly created accounts directly into the repository (`output/accounts.json`, `output/accounts.txt`, `output/tokens.txt`) and uploads artifact zips.
- **Incremental Deduplication**: Preserves all previously generated accounts across workflow runs without duplicates.

---

## 📁 Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── create_accounts.yml   # GitHub Actions automated workflow with auto-commit
├── solver/
│   ├── __init__.py
│   ├── best.onnx                 # Trained YOLOv8n ONNX puzzle gap detection model
│   ├── gap_yolo.py               # ONNX Runtime CPU inference engine (thread-limited)
│   ├── gap_cv.py                 # Hybrid gap detection wrapper
│   ├── realpage.py               # Aliyun Captcha 2.0 real-page solver & human kinematics
│   └── browser_helpers.py        # Stealth helper utilities
├── output/
│   ├── accounts.json             # Structured JSON list of all created accounts
│   ├── accounts.txt              # Formatted credentials (email:password)
│   └── tokens.txt                # Raw access tokens
├── main.py                       # CLI orchestrator & batch manager
├── mazdoor.py                    # Mazdoor Temporary Mail API client
├── config.py                     # Central configuration & URLs
├── requirements.txt              # Python dependencies
├── run.sh                        # Local runner script
└── README.md                     # Documentation
```

---

## 🚀 Running via GitHub Actions

1. Go to your repository on GitHub (`git@github.com:AwaisCh360/Qwen_V2.git`).
2. Navigate to the **Actions** tab.
3. Select **Create Qwen Accounts** workflow from the sidebar.
4. Click **Run workflow**:
   - **`count`**: Number of accounts to create (e.g. `3`).
   - **`delay`**: Delay in seconds between accounts (e.g. `5`).
5. Click the green **Run workflow** button.

Once complete:
- The generated accounts are automatically **committed and pushed** to `output/accounts.json`, `output/accounts.txt`, and `output/tokens.txt`.
- You can also download the ZIP artifact (`qwen-accounts-<run_id>`) directly from the workflow summary.

---

## 💻 Running Locally

### Requirements
- Python 3.10+
- macOS or Linux

### Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m cloakbrowser install

# 2. Run single account creation
./run.sh

# 3. Run batch creation (e.g. 3 accounts with 5s delay)
./run.sh --count 3 --delay 5
```

---

## 💾 Output Formats

All credentials are saved automatically in the `output/` directory:

### 1. `output/accounts.json`
```json
[
  {
    "accountNumber": 1,
    "fullName": "Judith Cruz",
    "qwenEmail": "adaptivesummit91@simulacrumcanvas.mazdoor.me",
    "qwenPassword": "Password123",
    "etempRecoverKey": "WKLBZOX9218412",
    "activationLink": null,
    "createdAt": "2026-10-16T17:15:23.000Z",
    "status": "activated",
    "token": "eyJhbGciOiJIUzI1NiIsImtpZCI6ImxlZ2FjeSI..."
  }
]
```

### 2. `output/accounts.txt`
```text
adaptivesummit91@simulacrumcanvas.mazdoor.me:Password123
airtadsmith30@woolanaunter.mazdoor.me:Password123
adsheartalundum97@mangroveallopath.mazdoor.me:Password123
```

### 3. `output/tokens.txt`
```text
eyJhbGciOiJIUzI1NiIsImtpZCI6ImxlZ2FjeSI...
eyJhbGciOiJIUzI1NiIsImtpZCI6ImxlZ2FjeSI...
eyJhbGciOiJIUzI1NiIsImtpZCI6ImxlZ2FjeSI...
```

---

## ⚡ Technical Highlights

| Component | Technology | Performance |
| :--- | :--- | :--- |
| **Vision Model** | YOLOv8n ONNX (`best.onnx`) | 15–30ms gap detection |
| **Kinematics Engine** | Ballistic Cubic Ease-Out + Reverse Drift | Passed Aliyun `T001` Heuristics |
| **Temporary Mail** | Mazdoor API (`mazdoor.me`) | 3–6s OTP delivery |
| **Browser Layer** | CloakBrowser Headless | Undetected Canvas & Fingerprints |
