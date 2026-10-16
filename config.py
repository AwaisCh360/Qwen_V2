import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Output Files
ACCOUNTS_JSON = OUTPUT_DIR / "accounts.json"
ACCOUNTS_TXT = OUTPUT_DIR / "accounts.txt"

# Solver Service (Local CloakBrowser API)
SOLVER_HOST = os.getenv("SOLVER_HOST", "http://127.0.0.1:8877")
SOLVER_URL = f"{SOLVER_HOST}/solve"
SOLVER_HEALTH = f"{SOLVER_HOST}/health"

# Mazdoor Mail Service
MAZDOOR_BASE_URL = os.getenv("MAZDOOR_BASE_URL", "https://berozgaar.mazdoor.me/api")
_env_key = os.getenv("MAZDOOR_API_KEY", "").strip()
MAZDOOR_API_KEY = _env_key if _env_key else "tk_0a65841dd0a074510cc79e8c16ee3ca18e9fe5a4d5f95634"

# Qwen Endpoints
QWEN_REGISTER_URL = "https://chat.qwen.ai/auth?mode=register"
QWEN_VERIFY_URL = "https://auth.qwen.ai/api/v2/auths/otp/email/verify"
QWEN_CONFIG_URL = "https://chat.qwen.ai/api/v2/configs/"
QWEN_USER_SETTINGS_URL = "https://chat.qwen.ai/api/v2/users/user/settings"

# Captcha Scene Details (Qwen Web)
SCENE_ID = "19x5u7lo"
PREFIX = "57d98d02303c01e7d2f7814c75224396"

# Timeouts (seconds)
SOLVER_TIMEOUT = 240
OTP_TIMEOUT = 90
REQUEST_TIMEOUT = 25

# Browser headers
DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "source": "web",
    "x-request-origin": "https://chat.qwen.ai",
    "origin": "https://chat.qwen.ai",
    "referer": "https://chat.qwen.ai/auth?mode=register",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}
