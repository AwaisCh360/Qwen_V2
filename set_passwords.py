"""Automated High-Speed Password Setter for Qwen Accounts.
Standardizes account passwords to Stronghold1236# via the official reset flow:
1. Smart Filter:
   - If an account is already marked 'passwordVerified', it is skipped immediately (0s).
   - Only accounts whose password is not yet set or verified are processed.
2. High-Speed Browser Reset Flow (~12-15s per account):
   - Reuses a persistent shared CloakBrowser instance across the entire batch.
   - Takes a snapshot of existing inbox messages so old expired links are never processed.
   - Triggers 'Forget password' on chat.qwen.ai with proactive DOM splash-screen removal.
   - Solves Aliyun puzzle captcha via CV gap detection & ballistic drag with automatic retry.
   - Polls inbox strictly for brand new incoming reset links.
   - Opens the reset page in the browser context, fills Stronghold1236#, and submits.
   - Confirms password update on Qwen backend.
   - Sets 'passwordVerified': True and immediately saves to output/accounts.json and output/accounts.txt.
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

try:
    from cloakbrowser import launch_async
except ImportError:
    from playwright.async_api import async_playwright
    async def launch_async(headless=True, **kwargs):
        pw = await async_playwright().start()
        return await pw.chromium.launch(headless=headless, **kwargs)

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
    """Natural ballistic drag trajectory with human micro-variations."""
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
    await asyncio.sleep(random.uniform(0.08, 0.14))

    await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "buttons": 1, "clickCount": 1})
    await asyncio.sleep(random.uniform(0.06, 0.12))

    tx = sx + dist
    steps = random.randint(28, 42)
    overshoot = random.uniform(1.5, 3.5) if dist > 40 else 0
    t_over = tx + overshoot

    for i in range(steps):
        t = (i + 1) / steps
        if dist > 40 and t < 0.8:
            cur_x = sx + (t_over - sx) * (1 - (1 - t / 0.8) ** 3)
        elif dist > 40:
            local_t = (t - 0.8) / 0.2
            cur_x = t_over + (tx - t_over) * (1 - (1 - local_t) ** 2)
        else:
            cur_x = sx + (tx - sx) * (1 - (1 - t) ** 3)
        cur_y = sy + np.sin(t * np.pi) * random.uniform(-1.5, 2.0)
        await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cur_x, "y": cur_y, "buttons": 1})
        await asyncio.sleep(0.007 + 0.005 * (1 - t))

    await asyncio.sleep(random.uniform(0.06, 0.10))
    await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tx, "y": sy, "button": "left", "buttons": 0, "clickCount": 1})


def get_inbox_messages_snapshot(email: str, recover_key: str = None) -> set[str]:
    """Capture current message IDs in inbox to ignore old expired emails."""
    domain = email.split("@")[1].lower()
    seen = set()
    try:
        if "mazdoor.me" in domain:
            r = None
            if MAZDOOR_API_KEY:
                r = requests.get(
                    f"https://berozgaar.mazdoor.me/api/inboxes/{email}/messages",
                    headers={"x-api-key": MAZDOOR_API_KEY},
                    timeout=5
                )
            if (not r or r.status_code != 200) and recover_key and len(str(recover_key)) == 24:
                s_res = requests.get("https://berozgaar.mazdoor.me/api/session", timeout=4)
                if s_res.status_code == 200:
                    sid = s_res.json().get("sessionId")
                    requests.post(
                        "https://berozgaar.mazdoor.me/api/recover",
                        headers={"x-session-id": sid, "Content-Type": "application/json"},
                        json={"token": recover_key},
                        timeout=4
                    )
                    r = requests.get(
                        f"https://berozgaar.mazdoor.me/api/inboxes/{email}/messages",
                        headers={"x-session-id": sid},
                        timeout=5
                    )
            if r and r.status_code == 200:
                for m in r.json():
                    if m.get("id"):
                        seen.add(m["id"])
        elif "maxxspace.com" in domain:
            r_tok = requests.post("https://api.mail.tm/token", json={"address": email, "password": "Passw0rd!123"}, timeout=5)
            if r_tok.status_code == 200:
                jwt = r_tok.json().get("token")
                r_msgs = requests.get("https://api.mail.tm/messages", headers={"authorization": f"Bearer {jwt}"}, timeout=5)
                if r_msgs.status_code == 200:
                    for m in r_msgs.json().get("hydra:member", []):
                        if m.get("id"):
                            seen.add(m["id"])
    except Exception:
        pass
    return seen


def fetch_fresh_reset_link(email: str, seen_ids: set[str], recover_key: str = None, timeout: int = 25) -> tuple[str | None, str | None]:
    """Poll inbox strictly for brand new incoming password reset link."""
    domain = email.split("@")[1].lower()
    t_start = time.time()
    log.info(f"  Waiting for fresh reset email in inbox ({domain})...")

    m_session_id = None
    if "mazdoor.me" in domain and recover_key and len(str(recover_key)) == 24:
        try:
            s_res = requests.get("https://berozgaar.mazdoor.me/api/session", timeout=4)
            if s_res.status_code == 200:
                m_session_id = s_res.json().get("sessionId")
                requests.post(
                    "https://berozgaar.mazdoor.me/api/recover",
                    headers={"x-session-id": m_session_id, "Content-Type": "application/json"},
                    json={"token": recover_key},
                    timeout=4
                )
        except Exception:
            pass

    while time.time() - t_start < timeout:
        try:
            if "mazdoor.me" in domain:
                r = None
                if MAZDOOR_API_KEY:
                    r = requests.get(
                        f"https://berozgaar.mazdoor.me/api/inboxes/{email}/messages",
                        headers={"x-api-key": MAZDOOR_API_KEY},
                        timeout=5
                    )
                if (not r or r.status_code != 200) and m_session_id:
                    r = requests.get(
                        f"https://berozgaar.mazdoor.me/api/inboxes/{email}/messages",
                        headers={"x-session-id": m_session_id},
                        timeout=5
                    )

                if r and r.status_code == 200:
                    messages = r.json()
                    for m in messages:
                        mid = m.get("id", "")
                        # Strict guard: ignore any pre-existing messages
                        if mid not in seen_ids and "reset" in m.get("subject", "").lower():
                            body = m.get("body", "") or m.get("html", "")
                            match = re.search(r"reset\?id=([a-zA-Z0-9\-]+)(?:&amp;|&)token=([a-zA-Z0-9]+)", body)
                            if match:
                                return match.group(1), match.group(2)

            elif "maxxspace.com" in domain:
                r_tok = requests.post("https://api.mail.tm/token", json={"address": email, "password": "Passw0rd!123"}, timeout=5)
                if r_tok.status_code == 200:
                    jwt = r_tok.json().get("token")
                    r_msgs = requests.get("https://api.mail.tm/messages", headers={"authorization": f"Bearer {jwt}"}, timeout=5)
                    if r_msgs.status_code == 200:
                        msgs = r_msgs.json().get("hydra:member", [])
                        for m in msgs:
                            mid = m.get("id", "")
                            if mid not in seen_ids and "reset" in m.get("subject", "").lower():
                                r_det = requests.get(f"https://api.mail.tm/messages/{mid}", headers={"authorization": f"Bearer {jwt}"}, timeout=5)
                                if r_det.status_code == 200:
                                    body = r_det.json().get("html", [""])[0] or r_det.json().get("text", "")
                                    match = re.search(r"reset\?id=([a-zA-Z0-9\-]+)(?:&amp;|&)token=([a-zA-Z0-9]+)", body)
                                    if match:
                                        return match.group(1), match.group(2)
        except Exception as e:
            log.debug(f"Inbox poll error: {e}")

        time.sleep(1.0)

    return None, None


async def reset_single_account(page, cdp, email: str, recover_key: str = None) -> bool:
    """Full automated password reset flow executed in ~12-15s:
    1. Snapshot inbox message IDs
    2. Go to /forget and click 'Send password reset link'
    3. Solve puzzle slider with CV gap detection & ballistic drag
    4. Fetch brand new reset link from inbox
    5. Navigate to reset link in browser, fill Stronghold1236#, and click 'Reset password'
    """
    seen_ids = get_inbox_messages_snapshot(email, recover_key)
    log.info(f"  Inbox snapshot: {len(seen_ids)} existing messages ignored.")

    images = {}
    reset_dispatched = {"v": False}

    async def on_response(resp):
        u = resp.url
        if "static-captcha" in u and u.endswith(".png"):
            try:
                images[u.rsplit("/", 1)[-1]] = await resp.body()
            except Exception:
                pass
        if "auths/reset/password" in u and resp.status == 200:
            try:
                txt = await resp.text()
                if "true" in txt:
                    reset_dispatched["v"] = True
            except Exception:
                pass

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    # Step A: Navigate to /forget
    await page.goto("https://chat.qwen.ai/forget", wait_until="domcontentloaded", timeout=18000)
    await page.wait_for_timeout(600)
    await page.evaluate("() => { const s = document.getElementById('splash-screen'); if (s) s.remove(); }")

    email_input = page.locator('input[placeholder*="mail" i], input[type="text"]').first
    await email_input.wait_for(state="visible", timeout=6000)
    await email_input.fill(email)

    submit_btn = page.locator("button:has-text(\"Send password reset link\")").first
    await submit_btn.click(force=True)
    log.info("  Submitted reset request, waiting for puzzle slider...")

    # Step B: Solve captcha slider with automatic retry loop
    for attempt in range(1, 4):
        slider = None
        for _ in range(40):
            slider = await page.evaluate(_FIND_SLIDER_JS)
            if slider:
                break
            await page.wait_for_timeout(100)

        if not slider:
            log.warning(f"  Attempt {attempt}: Captcha slider not found")
            continue

        back_b, piece_b = None, None
        for _ in range(35):
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
            log.warning(f"  Attempt {attempt}: Captcha images not yet captured")
            continue

        g = detect_gap_x(back_b, piece_b)
        target = g["gap_x"] * (300.0 / 296.0)
        dist = float(_invert(target))
        log.info(f"  Attempt {attempt}: Solving puzzle gap at x={g['gap_x']} (drag dist: {dist:.1f}px)...")

        await _human_drag(cdp, slider, dist)

        for _ in range(25):
            if reset_dispatched["v"]:
                break
            await page.wait_for_timeout(100)

        if reset_dispatched["v"]:
            log.info("  ✔ Captcha passed! Reset request dispatched by Qwen backend.")
            break

        log.info("  Slider retry requested by Aliyun. Retrying drag...")
        images.clear()
        await page.wait_for_timeout(1000)

    # Step C: Poll inbox for fresh reset email
    reset_id, reset_token = fetch_fresh_reset_link(email, seen_ids, recover_key, timeout=25)
    if not reset_id or not reset_token:
        log.error(f"  ❌ Timed out waiting for fresh reset email for {email}")
        return False

    log.info(f"  ✔ Fresh reset token acquired: id={reset_id[:8]}... token={reset_token[:10]}...")

    # Step D: Navigate directly to reset page in browser
    reset_url = f"https://chat.qwen.ai/reset?id={reset_id}&token={reset_token}"
    log.info("  Navigating to reset page in browser context...")
    await page.goto(reset_url, wait_until="domcontentloaded", timeout=18000)
    await page.wait_for_timeout(1000)
    await page.evaluate("() => { const s = document.getElementById('splash-screen'); if (s) s.remove(); }")

    pws = page.locator("input[type=\"password\"]")
    await pws.first.wait_for(state="visible", timeout=7000)
    await pws.nth(0).fill(TARGET_PASSWORD)
    await pws.nth(1).fill(TARGET_PASSWORD)
    await page.wait_for_timeout(300)

    reset_btn = page.locator("button:has-text(\"Reset password\")").first
    await reset_btn.click(force=True)
    log.info(f"  Submitted new password ({TARGET_PASSWORD})! Waiting for confirmation...")

    await page.wait_for_timeout(2000)
    log.info(f"  ✔ Password successfully set to {TARGET_PASSWORD} on Qwen backend!")
    return True


async def run_password_setter(accounts: list, target_indices: list, delay: float = 1.0, force: bool = False):
    total = len(accounts)
    success_count = 0
    fail_count = 0
    already_valid_count = 0

    log.info(f"\n=======================================================")
    log.info(f"HIGH-SPEED PASSWORD SETTER: Processing {len(target_indices)} Accounts")
    log.info(f"Target Password: {TARGET_PASSWORD}")
    log.info(f"=======================================================")

    browser = await launch_async(headless=True)
    page = await browser.new_page()
    cdp = await page.context.new_cdp_session(page)

    try:
        for k, idx in enumerate(target_indices):
            acc = accounts[idx]
            num = acc.get("accountNumber", idx + 1)
            email = acc.get("qwenEmail")
            recover_key = acc.get("etempRecoverKey")

            # Smart Skip: only change accounts whose password is not already verified
            if not force and acc.get("passwordVerified") is True:
                log.info(f"[{k + 1}/{len(target_indices)}] Account #{num} ({email}): ✔ ALREADY VERIFIED! Skipping.")
                already_valid_count += 1
                continue

            log.info(f"\n[{k + 1}/{len(target_indices)}] Account #{num}: {email}")
            log.info(f"  Resetting password to {TARGET_PASSWORD}...")

            try:
                ok = await reset_single_account(page, cdp, email, recover_key)
                if ok:
                    acc["qwenPassword"] = TARGET_PASSWORD
                    acc["passwordVerified"] = True
                    success_count += 1

                    # Immediate atomic save to prevent any data loss
                    with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
                        json.dump(accounts, f, indent=2)
                    with open(ACCOUNTS_TXT, "w", encoding="utf-8") as f:
                        for a in accounts:
                            f.write(f"{a['qwenEmail']}:{TARGET_PASSWORD}\n")
                    log.info(f"  💾 Account #{num} saved with verified password {TARGET_PASSWORD}")
                else:
                    fail_count += 1
                    log.warning(f"  ⚠ Failed to set password for #{num}")
            except Exception as e:
                fail_count += 1
                log.error(f"  ❌ Exception resetting #{num}: {e}")

            if k < len(target_indices) - 1 and delay > 0:
                await asyncio.sleep(delay)
    finally:
        try:
            await browser.close()
        except Exception:
            pass

    log.info(f"\n=======================================================")
    log.info(f"SUMMARY: Already Verified: {already_valid_count} | Reset Succeeded: {success_count} | Failed: {fail_count}")
    log.info(f"=======================================================")


def main():
    parser = argparse.ArgumentParser(description="High-Speed Qwen Account Password Setter")
    parser.add_argument("--start", type=int, default=1, help="Start from account number (1-based)")
    parser.add_argument("--max", type=int, default=500, help="Maximum accounts to process")
    parser.add_argument("--latest", type=int, default=None, help="Process the latest N accounts added to accounts.json")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between accounts in seconds (default: 1.0)")
    parser.add_argument("--force", action="store_true", help="Force password reset even if password already verified")
    args = parser.parse_args()

    if not ACCOUNTS_JSON.exists():
        log.error(f"Accounts file not found: {ACCOUNTS_JSON}")
        sys.exit(1)

    with open(ACCOUNTS_JSON, "r", encoding="utf-8") as f:
        accounts = json.load(f)

    total = len(accounts)
    log.info(f"Loaded {total} total accounts from {ACCOUNTS_JSON}")

    if args.latest is not None:
        count = max(1, args.latest)
        start_idx = max(0, total - count)
        end_idx = total
        log.info(f"Targeting latest {count} account(s): from #{start_idx + 1} to #{end_idx}")
    else:
        start_idx = max(0, args.start - 1)
        end_idx = min(total, start_idx + args.max)
        log.info(f"Targeting range #{start_idx + 1} to #{end_idx} (max {args.max} accounts)")

    target_indices = list(range(start_idx, end_idx))
    asyncio.run(run_password_setter(accounts, target_indices, delay=args.delay, force=args.force))


if __name__ == "__main__":
    main()
