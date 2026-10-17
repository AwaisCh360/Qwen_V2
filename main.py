#!/usr/bin/env python3
"""
Qwen HTTP Account Maker
=======================
Automated Qwen Account Generator using Mazdoor Temporary Mail API,
local Aliyun Captcha Solver API (:8877), and Qwen's Auth HTTP endpoints.
"""

import sys
import json
import time
import random
import argparse
import subprocess
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import requests

import config
from mazdoor import MazdoorMail

# Terminal ANSI colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_BLUE = "\033[34m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"

def log_header():
    print(f"\n{C_CYAN}{'='*65}{C_RESET}")
    print(f"{C_BOLD}{C_GREEN} ⚡ QWEN HTTP ACCOUNT MAKER (API-DRIVEN){C_RESET}")
    print(f"{C_CYAN} 📡 Captcha Solver: {config.SOLVER_HOST}{C_RESET}")
    print(f"{C_CYAN} 📧 Email Provider: {config.MAZDOOR_BASE_URL}{C_RESET}")
    print(f"{C_CYAN}{'='*65}{C_RESET}\n")

def check_or_start_solver(auto_start: bool = True) -> bool:
    """Check if the local solver daemon is running, start it if needed."""
    try:
        r = requests.get(config.SOLVER_HEALTH, timeout=3)
        if r.status_code == 200 and r.json().get("status") == "ok":
            print(f"{C_GREEN}✔ Captcha Solver is online and ready.{C_RESET}")
            return True
    except Exception:
        pass

    # Check if embedded solver is present in repository
    embedded_solver = config.BASE_DIR / "solver" / "realpage.py"
    if embedded_solver.exists():
        print(f"{C_GREEN}✔ Embedded solver engine available (standalone headless mode).{C_RESET}")
        return True

    print(f"{C_YELLOW}⚠ Captcha Solver API is not running on {config.SOLVER_HOST}.{C_RESET}")
    solver_dir = config.BASE_DIR.parent / "captcha-solver"
    solver_script = solver_dir / "server.py"

    if not solver_script.exists():
        print(f"{C_RED}❌ Neither API solver on :8877 nor local solver script found.{C_RESET}")
        return False

    if auto_start:
        print(f"{C_CYAN}🚀 Launching Captcha Solver daemon in background...{C_RESET}")
        venv_py = solver_dir / ".venv" / "bin" / "python"
        py_exec = str(venv_py) if venv_py.exists() else sys.executable
        subprocess.Popen(
            [py_exec, "server.py"],
            cwd=str(solver_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        for _ in range(15):
            time.sleep(1)
            try:
                r = requests.get(config.SOLVER_HEALTH, timeout=2)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    print(f"{C_GREEN}✔ Captcha Solver launched successfully!{C_RESET}")
                    return True
            except Exception:
                continue

    print(f"{C_RED}❌ Could not connect to Captcha Solver.{C_RESET}")
    return False

FIRST_NAMES = [
    'James', 'Mary', 'Robert', 'Patricia', 'John', 'Jennifer', 'Michael', 'Linda',
    'David', 'Elizabeth', 'William', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica',
    'Thomas', 'Sarah', 'Charles', 'Karen', 'Christopher', 'Nancy', 'Daniel', 'Margaret',
    'Matthew', 'Lisa', 'Anthony', 'Betty', 'Mark', 'Sandra', 'Donald', 'Ashley',
    'Steven', 'Kimberly', 'Paul', 'Emily', 'Andrew', 'Donna', 'Joshua', 'Michelle',
    'Kenneth', 'Carol', 'Kevin', 'Amanda', 'Brian', 'Dorothy', 'George', 'Melissa',
    'Edward', 'Deborah', 'Ronald', 'Stephanie', 'Timothy', 'Rebecca', 'Jason', 'Sharon',
    'Jeffrey', 'Laura', 'Ryan', 'Cynthia', 'Jacob', 'Kathleen', 'Gary', 'Amy',
    'Nicholas', 'Shirley', 'Eric', 'Angela', 'Jonathan', 'Helen', 'Stephen', 'Anna',
    'Larry', 'Brenda', 'Justin', 'Pamela', 'Scott', 'Nicole', 'Brandon', 'Emma',
    'Benjamin', 'Samantha', 'Samuel', 'Katherine', 'Gregory', 'Christine', 'Frank', 'Debra',
    'Alexander', 'Rachel', 'Raymond', 'Catherine', 'Patrick', 'Carolyn', 'Jack', 'Janet',
    'Dennis', 'Ruth', 'Jerry', 'Maria', 'Tyler', 'Heather', 'Aaron', 'Diane',
    'Henry', 'Virginia', 'Douglas', 'Julie', 'Jose', 'Joyce', 'Peter', 'Victoria',
    'Adam', 'Olivia', 'Nathan', 'Kelly', 'Zachary', 'Christina', 'Walter', 'Lauren',
    'Kyle', 'Joan', 'Harold', 'Evelyn', 'Carl', 'Judith', 'Arthur', 'Andrea',
    'Gerald', 'Hannah', 'Roger', 'Megan', 'Keith', 'Cheryl', 'Jeremy', 'Jacqueline',
    'Terry', 'Martha', 'Lawrence', 'Gloria', 'Sean', 'Teresa', 'Christian', 'Ann',
    'Ethan', 'Sara', 'Austin', 'Madison', 'Joe', 'Frances', 'Albert', 'Kathryn',
    'Jesse', 'Janice', 'Willie', 'Jean', 'Billy', 'Abigail', 'Bryan', 'Alice',
    'Bruce', 'Judy', 'Jordan', 'Sophia', 'Dylan', 'Grace', 'Noah', 'Denise',
    'Alan', 'Amber', 'Ralph', 'Doris', 'Gabriel', 'Marilyn', 'Logan', 'Danielle',
    'Wayne', 'Beverly', 'Vincent', 'Isabella', 'Eugene', 'Theresa', 'Randy', 'Diana',
    'Harry', 'Natalie', 'Philip', 'Brittany', 'Louis', 'Charlotte', 'Bobby', 'Marie',
    'Johnny', 'Kayla', 'Mason', 'Alexis', 'Eduardo', 'Lori'
]

LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
    'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
    'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker',
    'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill',
    'Flores', 'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell',
    'Mitchell', 'Carter', 'Roberts', 'Gomez', 'Phillips', 'Evans', 'Turner', 'Diaz',
    'Parker', 'Cruz', 'Edwards', 'Collins', 'Reyes', 'Stewart', 'Morris', 'Morales',
    'Murphy', 'Cook', 'Rogers', 'Gutierrez', 'Ortiz', 'Morgan', 'Cooper', 'Peterson',
    'Bailey', 'Reed', 'Kelly', 'Howard', 'Ramos', 'Kim', 'Cox', 'Ward',
    'Richardson', 'Watson', 'Brooks', 'Chavez', 'Wood', 'James', 'Bennett', 'Gray',
    'Mendoza', 'Ruiz', 'Hughes', 'Price', 'Alvarez', 'Castillo', 'Sanders', 'Patel',
    'Myers', 'Long', 'Ross', 'Foster', 'Jimenez', 'Powell', 'Jenkins', 'Perry',
    'Russell', 'Sullivan', 'Bell', 'Coleman', 'Butler', 'Henderson', 'Barnes', 'Gonzales',
    'Fisher', 'Vasquez', 'Simmons', 'Romero', 'Jordan', 'Patterson', 'Alexander', 'Hamilton',
    'Graham', 'Reynolds', 'Griffin', 'Wallace', 'Moreno', 'West', 'Cole', 'Hayes',
    'Bryant', 'Herrera', 'Gibson', 'Ellis', 'Tran', 'Medina', 'Aguilar', 'Stevens',
    'Murray', 'Ford', 'Castro', 'Marshall', 'Owens', 'Harrison', 'Fernandez', 'Mcdonald',
    'Woods', 'Washington', 'Kennedy', 'Wells', 'Vargas', 'Henry', 'Chen', 'Freeman',
    'Webb', 'Tucker', 'Guzman', 'Burns', 'Crawford', 'Olson', 'Simpson', 'Porter',
    'Hunter', 'Gordon', 'Mendez', 'Silva', 'Shaw', 'Snyder', 'Mills', 'Pearson'
]

DEFAULT_PASSWORD = "Stronghold1236#"

def _gen_full_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def _gen_password() -> str:
    return DEFAULT_PASSWORD

def save_account(
    email: str,
    token: str,
    cookies: dict | None = None,
    password: str | None = None,
    full_name: str | None = None,
    recover_key: str | None = None,
    status: str = "activated"
) -> bool:
    """Persist generated account in the exact required schema to output/accounts.json and output/accounts.txt.
    STRICT GUARD: Refuses to save any account lacking a valid JWT Bearer token.
    """
    if not token or not isinstance(token, str) or not token.strip() or token == "NO_TOKEN":
        print(f"{C_RED}⛔ REJECTED: Refusing to save account '{email}' without a valid Bearer token.{C_RESET}")
        return False

    clean_token = token.strip()
    if not full_name:
        full_name = _gen_full_name()
    if not password:
        password = _gen_password()
    if not recover_key:
        recover_key = (''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=7)) + str(random.randint(100000, 999999)))

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # Read existing accounts and determine next accountNumber
    accounts = []
    max_num = 0
    if config.ACCOUNTS_JSON.exists():
        try:
            raw = json.loads(config.ACCOUNTS_JSON.read_text())
            if isinstance(raw, list):
                for a in raw:
                    if not isinstance(a, dict):
                        continue
                    num = a.get("accountNumber")
                    if isinstance(num, int):
                        max_num = max(max_num, num)
                    accounts.append(a)
        except Exception:
            accounts = []

    account_num = max_num + 1

    # Exact format required by user
    entry = {
        "accountNumber": account_num,
        "fullName": full_name,
        "qwenEmail": email,
        "qwenPassword": password,
        "etempRecoverKey": recover_key,
        "activationLink": None,
        "createdAt": created_at,
        "status": status,
        "token": clean_token
    }

    # Avoid duplicate entry for the same email
    accounts = [a for a in accounts if a.get("qwenEmail") != email and a.get("email") != email]
    accounts.append(entry)
    config.ACCOUNTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    config.ACCOUNTS_JSON.write_text(json.dumps(accounts, indent=2))

    # Append to accounts.txt (email:password format)
    lines = []
    if config.ACCOUNTS_TXT.exists():
        try:
            existing_lines = config.ACCOUNTS_TXT.read_text().splitlines()
            for line in existing_lines:
                line = line.strip()
                if not line or ":NO_TOKEN" in line:
                    continue
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[1].strip() and parts[0].strip() != email:
                    lines.append(line)
        except Exception:
            lines = []

    lines.append(f"{email}:{password}")
    config.ACCOUNTS_TXT.write_text("\n".join(lines) + "\n")

    print(f"{C_GREEN}💾 Account #{account_num} ({full_name}) saved to: {config.ACCOUNTS_JSON}{C_RESET}")
    print(f"{C_GREEN}💾 Credentials appended to: {config.ACCOUNTS_TXT}{C_RESET}")
    return True

def verify_token_details(token: str) -> dict:
    """Call Qwen API with Bearer token to fetch user config."""
    try:
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {token}",
            "source": "web",
            "x-request-origin": "https://chat.qwen.ai",
            "user-agent": config.DEFAULT_HEADERS["user-agent"]
        }
        res = requests.get(config.QWEN_CONFIG_URL, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {}

def create_one_account(index: int = 1, total: int = 1, max_attempts: int = 2) -> bool:
    """Execute end-to-end account generation flow with automatic retry."""
    print(f"\n{C_MAGENTA}{'—'*65}{C_RESET}")
    print(f"{C_BOLD}{C_BLUE}[Account #{index}/{total}] Starting Account Creation Flow{C_RESET}")
    print(f"{C_MAGENTA}{'—'*65}{C_RESET}")

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"\n{C_YELLOW}🔄 [Retry #{attempt}/{max_attempts}] Retrying with a fresh inbox...{C_RESET}")

        # -------------------------------------------------------------
        # Step 1: Create Temporary Email Inbox
        # -------------------------------------------------------------
        print(f"\n{C_BOLD}[Step 1]{C_RESET} Generating temporary inbox via Mazdoor API...")
        mail = MazdoorMail()
        email = mail.create_inbox()
        if not email:
            print(f"{C_RED}❌ Failed to create Mazdoor email inbox.{C_RESET}")
            continue
        print(f"  {C_GREEN}✔ Generated Email:{C_RESET} {C_BOLD}{email}{C_RESET}")

        # -------------------------------------------------------------
        # Step 2: Solve Captcha & Send OTP (Hybrid: API or Direct)
        # -------------------------------------------------------------
        print(f"\n{C_BOLD}[Step 2]{C_RESET} Solving Captcha and dispatching OTP request...")
        t0 = time.time()
        solve_data = None

        # Check if local API solver on :8877 is reachable
        api_available = False
        try:
            h = requests.get(config.SOLVER_HEALTH, timeout=1.5)
            if h.status_code == 200 and h.json().get("status") == "ok":
                api_available = True
        except Exception:
            api_available = False

        if api_available:
            print(f"  {C_CYAN}📡 Using local Captcha Solver API (:8877)...{C_RESET}")
            payload = {
                "type": "aliyun",
                "real_page": True,
                "url": config.QWEN_REGISTER_URL,
                "scene_id": config.SCENE_ID,
                "prefix": config.PREFIX,
                "timeout_s": config.SOLVER_TIMEOUT,
                "pre_actions": [
                    {
                        "type": "fill",
                        "selector": "input[name=\"email\"], input[placeholder*=\"mail\" i]",
                        "value": email,
                        "timeout": 20000
                    },
                    {
                        "type": "click",
                        "selector": "button.qwenchat-email-otp-panel-button",
                        "timeout": 10000
                    }
                ]
            }
            try:
                resp = requests.post(config.SOLVER_URL, json=payload, timeout=config.SOLVER_TIMEOUT + 15)
                if resp.status_code == 200:
                    solve_data = resp.json()
            except Exception as e:
                print(f"{C_YELLOW}⚠ API call failed, falling back to direct solver: {e}{C_RESET}")

        if not solve_data:
            print(f"  {C_CYAN}🤖 Running embedded solver engine (Direct headless)...{C_RESET}")
            import asyncio
            from solver import solve_qwen_registration
            try:
                solve_data = asyncio.run(solve_qwen_registration(
                    url=config.QWEN_REGISTER_URL,
                    email=email,
                    mail=mail,
                    timeout_s=config.SOLVER_TIMEOUT,
                    max_attempts=10
                ))
            except Exception as e:
                print(f"{C_RED}❌ Direct solver exception: {e}{C_RESET}")
                continue

        elapsed = round(time.time() - t0, 1)
        if not solve_data or not solve_data.get("solved"):
            err_msg = solve_data.get("error") if solve_data else "unknown error"
            print(f"{C_RED}❌ Captcha solving failed in {elapsed}s: {err_msg}{C_RESET}")
            continue

        print(f"  {C_GREEN}✔ Captcha Passed in {elapsed}s! (Method: {solve_data.get('method', 'realpage')}){C_RESET}")

        token = solve_data.get("token")
        cookies = solve_data.get("cookies", {})
        otp_code = solve_data.get("otp_code")

        # If token was already obtained via in-browser verification
        if token:
            print(f"\n{C_BOLD}[Step 3 & 4]{C_RESET} {C_GREEN}✔ In-Browser Verification Complete!{C_RESET}")
            print(f"  {C_GREEN}🔑 Genuine Bearer Token Captured:{C_RESET} {C_BOLD}{C_CYAN}{token[:45]}...{C_RESET}")
        else:
            # -------------------------------------------------------------
            # Fallback: Wait for OTP Email from Mazdoor & Submit HTTP
            # -------------------------------------------------------------
            print(f"\n{C_BOLD}[Step 3]{C_RESET} Waiting for 6-digit OTP code in Mazdoor inbox...")
            otp_code = mail.get_otp_code(timeout=config.OTP_TIMEOUT)
            if not otp_code:
                print(f"{C_RED}❌ Timed out waiting for OTP email on {email}.{C_RESET}")
                continue
            print(f"  {C_GREEN}✔ OTP Code Received:{C_RESET} {C_BOLD}{C_CYAN}{otp_code}{C_RESET}")

            # -------------------------------------------------------------
            # Step 4: Verify OTP via Qwen HTTP Endpoint
            # -------------------------------------------------------------
            print(f"\n{C_BOLD}[Step 4]{C_RESET} Submitting OTP code to Qwen Auth API...")
            import uuid
            import datetime
            headers = dict(config.DEFAULT_HEADERS)
            headers["x-request-id"] = str(uuid.uuid4())
            tz_str = datetime.datetime.now().astimezone().strftime("%a %b %d %Y %H:%M:%S GMT%z")
            headers["timezone"] = tz_str

            body = {
                "identifier": email,
                "code": str(otp_code),
                "name": None
            }

            try:
                v_resp = requests.post(
                    config.QWEN_VERIFY_URL,
                    headers=headers,
                    json=body,
                    timeout=config.REQUEST_TIMEOUT
                )
                cookies = dict(v_resp.cookies)

                res_json = {}
                if v_resp.status_code == 200:
                    try:
                        res_json = v_resp.json()
                    except Exception:
                        pass

                    token = (
                        res_json.get("token")
                        or res_json.get("access_token")
                        or res_json.get("data", {}).get("token")
                        or res_json.get("data", {}).get("access_token")
                    )

                if not token:
                    token = cookies.get("token") or cookies.get("access_token") or cookies.get("session")

                if not token:
                    token = v_resp.headers.get("authorization") or v_resp.headers.get("x-access-token")

                if v_resp.status_code != 200:
                    print(f"{C_RED}❌ OTP verification failed (HTTP {v_resp.status_code}): {v_resp.text}{C_RESET}")
                    continue

                print(f"  {C_GREEN}✔ OTP Verified Successfully! (HTTP {v_resp.status_code}){C_RESET}")
                if res_json:
                    print(f"  {C_CYAN}📄 Verify Response:{C_RESET} {json.dumps(res_json)}")
            except Exception as e:
                print(f"{C_RED}❌ Exception submitting OTP: {e}{C_RESET}")
                continue

        # Strict check: Require genuine Bearer token
        if not token or not isinstance(token, str) or not token.strip() or token == "NO_TOKEN":
            print(f"\n{C_RED}❌ Verification failed: No valid access token obtained for {email}. Account will NOT be saved.{C_RESET}")
            continue

        print(f"  {C_CYAN}🔑 Access Token:{C_RESET} {token[:40]}...")

        # Verify token by calling Qwen Config endpoint if available
        cfg = verify_token_details(token)
        if cfg:
            print(f"  {C_GREEN}✔ Account token verified against chat.qwen.ai API!{C_RESET}")

        # ---------------------------------------------------------
        # Step 5: Set Permanent Password on Qwen Backend
        # ---------------------------------------------------------
        print(f"\n{C_BOLD}[Step 5]{C_RESET} Setting permanent password ({DEFAULT_PASSWORD}) on Qwen backend...")
        try:
            from set_passwords import reset_account_password
            pw_ok, fresh_token = asyncio.run(reset_account_password(email, recover_key=mail.session_id if mail else None))
            if pw_ok:
                print(f"  {C_GREEN}✔ Password successfully registered as {DEFAULT_PASSWORD} on Qwen backend!{C_RESET}")
                if fresh_token:
                    token = fresh_token
                    print(f"  {C_GREEN}✔ Upgraded to genuine 30-day token!{C_RESET}")
            else:
                print(f"  {C_YELLOW}⚠ Immediate reset skipped/deferred to workflow step.{C_RESET}")
        except Exception as e:
            print(f"  {C_YELLOW}⚠ Password setting notice: {e}{C_RESET}")

        # ---------------------------------------------------------
        # Step 6: Save Credentials (STRICT GUARD)
        # ---------------------------------------------------------
        saved = save_account(
            email=email,
            token=token,
            cookies=cookies,
            password=DEFAULT_PASSWORD,
            recover_key=mail.session_id if mail else None,
            status="activated"
        )
        if saved:
            print(f"\n{C_BOLD}{C_GREEN}🎉 ACCOUNT #{index} SUCCESSFULLY CREATED AND VERIFIED! 🎉{C_RESET}")
            return True
        else:
            print(f"{C_RED}❌ Failed to save account {email}.{C_RESET}")
            continue

    print(f"\n{C_RED}❌ Account #{index} failed after {max_attempts} attempts.{C_RESET}")
    return False

def main():
    parser = argparse.ArgumentParser(description="Qwen HTTP Account Maker")
    parser.add_argument("--count", "-c", type=int, default=1, help="Number of accounts to create (default: 1)")
    parser.add_argument("--delay", "-d", type=int, default=3, help="Delay between creations in seconds (default: 3)")
    parser.add_argument("--no-auto-solver", action="store_true", help="Do not attempt to auto-launch solver")
    args = parser.parse_args()

    log_header()

    # Ensure solver is running
    if not check_or_start_solver(auto_start=not args.no_auto_solver):
        sys.exit(1)

    successful = 0
    total = args.count

    for i in range(1, total + 1):
        ok = create_one_account(index=i, total=total)
        if ok:
            successful += 1

        if i < total:
            print(f"\n{C_YELLOW}⏳ Waiting {args.delay}s before starting next account...{C_RESET}")
            time.sleep(args.delay)

    print(f"\n{C_CYAN}{'='*65}{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}🏁 BATCH COMPLETED:{C_RESET} {successful}/{total} accounts successfully created.")
    print(f"{C_CYAN}📂 Output folder: {config.OUTPUT_DIR}{C_RESET}")
    print(f"{C_CYAN}{'='*65}{C_RESET}\n")

if __name__ == "__main__":
    main()
