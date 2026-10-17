"""Automated Password Setter & Token Refresher for Qwen Accounts.
Standardizes all account passwords to Stronghold1236# via the official reset flow:
1. Tests password login. If already working, captures token and proceeds.
2. If password not set, triggers 'Forget password' on chat.qwen.ai.
3. Automatically solves the Aliyun puzzle captcha using CV gap detection and kinematic mouse drag.
4. Reads reset email from Mazdoor API or mail.tm.
5. Submits new password Stronghold1236# to auth.qwen.ai/api/v2/users/reset/password.
6. Performs password login to capture fresh bearer token.
7. Saves updated accounts to output/accounts.json and output/accounts.txt.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import logging
import random
import re
import sys
import time
import os
from pathlib import Path

import numpy as np
import requests
from cloakbrowser import launch_async

from solver.gap_cv import detect_gap_x

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("set_passwords")

BASE_DIR = Path(__file__).resolve().parent
ACCOUNTS_JSON = BASE_DIR / "output" / "accounts.json"
ACCOUNTS_TXT = BASE_DIR / "output" / "accounts.txt"

TARGET_PASSWORD = "Stronghold1236#"
TARGET_PASSWORD_HASH = hashlib.sha256(TARGET_PASSWORD.encode()).hexdigest()
MAZDOOR_API_KEY = os.getenv("MAZDOOR_API_KEY", "tk_0a65841dd0a074510cc79e8c16ee3ca18e9fe5a4d5f95634").strip()

_COEF = (0.00355, 0.0769, -0.004)

def _invert(target_px: float) -> float:
    a, b, c = _COEF
    disc = max(0.0, b * b - 4 * a * (c - target_px))
    return (-b + np.sqrt(disc)) / (2 * a)

_FIND_SLIDER_JS = """() => {
    const s = document.getElementById('aliyunCaptcha-sliding-slider');
    if (!s) return null;
    const r = s.getBoundingClientRect();
    return (r.width > 0 && r.height > 0) ? {
        x: r.x + r.width / 2,
        y: r.y + r.height / 2,
        w: r.width,
        h: r.height
    } : null;
}"""

async def _human_drag(cdp, slider: dict, dist: float):
    max_track = 254.0
    dist = max(10.0, min(max_track, dist))
    sx, sy = slider["x"], slider["y"]
    viewport_w, viewport_h = 1280, 800
    start_mouse_x = random.uniform(viewport_w * 0.3, viewport_w * 0.6)
    start_mouse_y = random.uniform(viewport_h * 0.3, viewport_h * 0.6)

    approach_steps = 15
    for k in range(1, approach_steps + 1):
        at = k / approach_steps
        ax = start_mouse_x + (sx - start_mouse_x) * at
        ay = start_mouse_y + (sy - start_mouse_y) * at
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": ax, "y": ay, "buttons": 0})
        await asyncio.sleep(0.012)
    await asyncio.sleep(random.uniform(0.08, 0.15))

    await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "buttons": 1, "clickCount": 1})
    await asyncio.sleep(random.uniform(0.06, 0.12))

    tx = sx + dist
    steps = random.randint(28, 42)
    overshoot = random.uniform(1.5, 4.0) if dist > 40 else 0
    t_over = tx + overshoot

    for i in range(steps):
        t = (i + 1) / steps
        if t < 0.8:
            cur_x = sx + (t_over - sx) * (1 - (1 - t / 0.8) ** 2)
        else:
            local_t = (t - 0.8) / 0.2
            cur_x = t_over + (tx - t_over) * (1 - (1 - local_t) ** 2)
        cur_y = sy + np.sin(t * np.pi) * random.uniform(-1.5, 2.5)
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cur_x, "y": cur_y, "buttons": 1})
        await asyncio.sleep(0.007 + 0.005 * (1 - t))

    await asyncio.sleep(random.uniform(0.05, 0.10))
    await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tx, "y": sy, "button": "left", "buttons": 0, "clickCount": 1})


def fetch_reset_link_from_inbox(email: str, recover_key: str = None, timeout: int = 30) -> tuple[str, str]:
    """Poll inbox for the Qwen password reset link."""
    domain = email.split("@")[1].lower()
    t_start = time.time()
    log.info(f"  Waiting for reset email in inbox ({domain})...")

    while time.time() - t_start < timeout:
        try:
            if "mazdoor.me" in domain:
                # Try API key first
                r = requests.get(
                    f"https://berozgaar.mazdoor.me/api/inboxes/{email}/messages",
                    headers={"x-api-key": MAZDOOR_API_KEY},
                    timeout=8
                )
                if r.status_code != 200 and recover_key:
                    # Fallback to session id
                    r = requests.get(
                        f"https://berozgaar.mazdoor.me/api/inboxes/{email}/messages",
                        headers={"x-session-id": recover_key},
                        timeout=8
                    )
                if r.status_code == 200:
                    messages = r.json()
                    for m in messages:
                        if "reset" in m.get("subject", "").lower():
                            body = m.get("body", "")
                            # Match id and token
                            match = re.search(r"reset\?id=([a-zA-Z0-9\-]+)(?:&amp;|&)token=([a-zA-Z0-9]+)", body)
                            if match:
                                return match.group(1), match.group(2)
            elif "maxxspace.com" in domain:
                r_tok = requests.post("https://api.mail.tm/token", json={"address": email, "password": "Passw0rd!123"}, timeout=8)
                if r_tok.status_code == 200:
                    jwt_token = r_tok.json().get("token")
                    r_msgs = requests.get("https://api.mail.tm/messages", headers={"authorization": f"Bearer {jwt_token}"}, timeout=8)
                    if r_msgs.status_code == 200:
                        data = r_msgs.json()
                        msgs = data.get("hydra:member", [])
                        for m in msgs:
                            if "reset" in m.get("subject", "").lower():
                                msg_id = m.get("id")
                                r_detail = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers={"authorization": f"Bearer {jwt_token}"}, timeout=8)
                                if r_detail.status_code == 200:
                                    body = r_detail.json().get("html", [""])[0] or r_detail.json().get("text", "")
                                    match = re.search(r"reset\?id=([a-zA-Z0-9\-]+)(?:&amp;|&)token=([a-zA-Z0-9]+)", body)
                                    if match:
                                        return match.group(1), match.group(2)
        except Exception as e:
            log.debug(f"Inbox poll error: {e}")

        time.sleep(2.5)

    return None, None


def submit_password_reset(reset_id: str, reset_token: str) -> bool:
    """Submit new password to Qwen reset API."""
    url = "https://auth.qwen.ai/api/v2/users/reset/password"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "source": "web",
        "timezone": "Sat Oct 17 2026 07:00:00 GMT+0500",
        "x-request-origin": "https://chat.qwen.ai",
        "referer": f"https://chat.qwen.ai/reset?id={reset_id}&token={reset_token}",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    payload = {
        "id": reset_id,
        "token": reset_token,
        "language": "en-US",
        "new_password": TARGET_PASSWORD_HASH
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        if r.status_code == 200 and r.json().get("success"):
            return True
        log.warning(f"  Reset API returned: {r.status_code} - {r.text}")
    except Exception as e:
        log.error(f"  Reset API exception: {e}")
    return False


async def try_password_login(page, email: str) -> str:
    """Attempt sign-in via password on chat.qwen.ai and return token if successful."""
    await page.goto("https://chat.qwen.ai/auth", wait_until="domcontentloaded", timeout=35000)
    await page.wait_for_timeout(2000)

    try:
        pw_btn = page.locator("button:has-text(\"Log in with a password\")").first
        if await pw_btn.is_visible():
            await pw_btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

    email_inp = page.locator("input[placeholder*=\"mail\" i]").first
    await email_inp.fill(email)
    pw_inp = page.locator("input[type=\"password\"]").first
    await pw_inp.fill(TARGET_PASSWORD)

    submit_btn = page.locator("button:has-text(\"Log in\")").last
    await submit_btn.click()
    await page.wait_for_timeout(3500)

    if "chat.qwen.ai" in page.url and "/auth" not in page.url:
        token = await page.evaluate("""() => {
            return localStorage.getItem("token") || localStorage.getItem("access_token") || localStorage.getItem("auth_token") || null;
        }""")
        return token

    return None


async def reset_account_password(email: str, recover_key: str = None) -> tuple[bool, str]:
    """Execute complete automated reset flow for a single account."""
    log.info(f"▶ Launching browser session for {email}...")
    browser = await launch_async(headless=True)
    page = await browser.new_page()
    cdp = await page.context.new_cdp_session(page)

    images = {}
    reset_dispatched = {"v": False}

    async def on_response(resp):
        u = resp.url
        if "static-captcha" in u and u.endswith(".png"):
            try:
                images[u.rsplit("/", 1)[-1]] = await resp.body()
            except Exception:
                pass
        if "reset/password" in u:
            try:
                txt = await resp.text()
                if '"success":true' in txt.replace(" ", "") or resp.status == 200:
                    reset_dispatched["v"] = True
            except Exception:
                pass

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    # Step 1: Check if already can sign in with target password
    log.info(f"  Step 1: Checking if password is already {TARGET_PASSWORD}...")
    token = await try_password_login(page, email)
    if token:
        log.info(f"  ✔ Account already authenticated with {TARGET_PASSWORD}!")
        await browser.close()
        return True, token

    log.info("  Password not yet set or sign-in required reset. Triggering 'Forget password'...")

    # Step 2: Trigger Forget password
    await page.goto("https://chat.qwen.ai/auth", wait_until="domcontentloaded", timeout=35000)
    await page.wait_for_timeout(2000)

    try:
        pw_btn = page.locator("button:has-text(\"Log in with a password\")").first
        await pw_btn.wait_for(state="visible", timeout=8000)
        await pw_btn.click()
        await page.wait_for_timeout(1000)
    except Exception as e:
        log.warning(f"  Could not click 'Log in with a password': {e}")

    try:
        forget_btn = page.locator("button:has-text(\"Forget password\")").first
        await forget_btn.wait_for(state="visible", timeout=8000)
        await forget_btn.click()
        await page.wait_for_timeout(1500)
    except Exception as e:
        log.warning(f"  Could not click 'Forget password': {e}")

    email_input = page.locator('input[placeholder*="mail" i], input[type="text"]').first
    await email_input.wait_for(state="visible", timeout=8000)
    await email_input.fill(email)

    submit_btn = page.locator("button:has-text(\"Send password reset link\")").first
    await submit_btn.click()
    log.info("  Submitted reset request, waiting for puzzle slider...")

    # Step 3: Solve slider
    slider = None
    for _ in range(50):
        slider = await page.evaluate(_FIND_SLIDER_JS)
        if slider:
            break
        await page.wait_for_timeout(100)

    if not slider:
        log.error("  ❌ Captcha slider did not appear")
        await browser.close()
        return False, None

    back_b = None
    piece_b = None
    for _ in range(40):
        if not back_b:
            for k, b in list(images.items()):
                if len(b) > 10000:
                    back_b = b
                    break
        if not piece_b:
            for k, b in list(images.items()):
                if len(b) < 10000:
                    piece_b = b
                    break
        if back_b and piece_b:
            break
        await page.wait_for_timeout(100)

    if not back_b or not piece_b:
        log.error("  ❌ Failed to capture captcha puzzle images")
        await browser.close()
        return False, None

    g = detect_gap_x(back_b, piece_b)
    geo = await page.evaluate("""() => {
        const bg = document.getElementById('aliyunCaptcha-img');
        if (!bg) return null;
        const r = bg.getBoundingClientRect();
        return (r.width > 50 && bg.naturalWidth > 50) ? { w: r.width, natW: bg.naturalWidth } : null;
    }""")
    if not geo:
        geo = {"w": 300, "natW": 296}
    scale = geo["w"] / geo["natW"]
    if scale < 0.8 or scale > 1.3:
        scale = 300.0 / 296.0

    target = g["gap_x"] * scale
    dist = float(_invert(target))
    log.info(f"  Solving puzzle gap at x={g['gap_x']} (drag dist: {dist:.1f}px)...")

    await _human_drag(cdp, slider, dist)

    for _ in range(50):
        if reset_dispatched["v"]:
            break
        await page.wait_for_timeout(200)

    await page.wait_for_timeout(2000)
    await browser.close()

    # Step 4: Fetch reset link from inbox
    reset_id, reset_token = fetch_reset_link_from_inbox(email, recover_key, timeout=30)
    if not reset_id or not reset_token:
        log.error(f"  ❌ Timed out waiting for reset link email for {email}")
        return False, None

    log.info(f"  ✔ Reset token acquired: id={reset_id[:8]}... token={reset_token[:10]}...")

    # Step 5: Submit new password to API
    log.info(f"  Submitting new password ({TARGET_PASSWORD}) to Qwen API...")
    ok = submit_password_reset(reset_id, reset_token)
    if not ok:
        log.error(f"  ❌ Password reset submission failed for {email}")
        return False, None

    log.info(f"  ✔ Password successfully updated to {TARGET_PASSWORD} on Qwen backend!")

    # Step 6: Log in with new password to get fresh 30-day token
    log.info("  Logging in with new password to capture 30-day token...")
    b_login = await launch_async(headless=True)
    p_login = await b_login.new_page()
    token = await try_password_login(p_login, email)
    await b_login.close()

    if token:
        log.info(f"  ✔ Fresh token captured: {token[:35]}...")
        return True, token
    else:
        log.info(f"  Password set, but browser did not return token immediately.")
        return True, None


def main():
    parser = argparse.ArgumentParser(description="Set Qwen account passwords to Stronghold1236#")
    parser.add_argument("--start", type=int, default=1, help="Start from account number (1-based)")
    parser.add_argument("--max", type=int, default=151, help="Maximum accounts to process")
    parser.add_argument("--latest", type=int, default=None, help="Process the latest N accounts added to accounts.json")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between accounts in seconds")
    args = parser.parse_args()

    if not ACCOUNTS_JSON.exists():
        log.error(f"Accounts file not found: {ACCOUNTS_JSON}")
        sys.exit(1)

    with open(ACCOUNTS_JSON, "r", encoding="utf-8") as f:
        accounts = json.load(f)

    total = len(accounts)
    log.info(f"Loaded {total} accounts from {ACCOUNTS_JSON}")

    if args.latest is not None:
        count = max(1, args.latest)
        start_idx = max(0, total - count)
        end_idx = total
        log.info(f"Targeting latest {count} account(s): from #{start_idx + 1} to #{end_idx}")
    else:
        start_idx = max(0, args.start - 1)
        end_idx = min(total, start_idx + args.max)

    success_count = 0
    fail_count = 0

    for i in range(start_idx, end_idx):
        acc = accounts[i]
        num = acc.get("accountNumber", i + 1)
        email = acc.get("qwenEmail")
        recover_key = acc.get("etempRecoverKey")

        log.info(f"\n=======================================================")
        log.info(f"[{i + 1}/{total}] Processing Account #{num}: {email}")
        log.info(f"=======================================================")

        try:
            ok, token = asyncio.run(reset_account_password(email, recover_key))
            if ok:
                acc["qwenPassword"] = TARGET_PASSWORD
                if token:
                    acc["token"] = token
                success_count += 1
                # Save immediately
                with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
                    json.dump(accounts, f, indent=2)
                # Also update txt
                with open(ACCOUNTS_TXT, "w", encoding="utf-8") as f:
                    for a in accounts:
                        f.write(f"{a['qwenEmail']}:{TARGET_PASSWORD}\n")
                log.info(f"  💾 Account #{num} saved with password {TARGET_PASSWORD}")
            else:
                fail_count += 1
                log.warning(f"  ⚠ Failed to set password for #{num}")
        except Exception as e:
            fail_count += 1
            log.error(f"  ❌ Exception on #{num}: {e}")

        if i < end_idx - 1 and args.delay > 0:
            time.sleep(args.delay)

    log.info(f"\n=======================================================")
    log.info(f"SUMMARY: Successfully processed {success_count}, Failed {fail_count}")
    log.info(f"=======================================================")

if __name__ == "__main__":
    main()
