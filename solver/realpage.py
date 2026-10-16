"""Aliyun Captcha 2.0 — Self-contained real-page solver for Qwen.
Navigates the real registration page, fills email, clicks Send OTP,
detects the puzzle gap, and drags the slider with quadratic ballistic trajectory.
"""
import asyncio
import base64
import json
import logging
import random
import time
from typing import Any, Optional

import numpy as np
from cloakbrowser import launch_async

from .gap_cv import detect_gap_x
from .browser_helpers import run_pre_actions

log = logging.getLogger("solver.realpage")

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

_HOOK_JS = r"""
(function () {
  var origBtoa = window.btoa.bind(window);
  window.__btoa_hits = [];
  window.btoa = function (str) {
    var out = origBtoa(str);
    try {
      if (typeof str === 'string' && str.indexOf('certifyId') !== -1 && str.indexOf('securityToken') !== -1) {
        window.__btoa_hits.push(str);
        window.__cb_success = str;
      }
    } catch (e) {}
    return out;
  };

  var _origInit = window.initAliyunCaptcha;
  Object.defineProperty(window, 'initAliyunCaptcha', {
    configurable: true,
    enumerable: true,
    get: function() { return _origInit; },
    set: function(fn) {
      _origInit = function(opts) {
        opts = opts || {};
        var origSuccess = opts.onBizSuccess;
        opts.onBizSuccess = function(data) {
          window.__cb_success = data;
          if (origSuccess) return origSuccess.apply(this, arguments);
        };
        return fn.call(this, opts);
      };
    }
  });
})();
"""

async def _human_drag(cdp, slider: dict, dist: float):
    """Natural ballistic kinematics with proper pointer events, wall boundary check, and approach."""
    max_track = 254.0
    dist = max(10.0, min(max_track, dist))

    sx, sy = slider["x"], slider["y"]

    # Natural hover approach from random screen position to slider handle
    viewport_w, viewport_h = 1280, 800
    start_mouse_x = random.uniform(viewport_w * 0.3, viewport_w * 0.6)
    start_mouse_y = random.uniform(viewport_h * 0.3, viewport_h * 0.6)

    approach_steps = 15
    for k in range(1, approach_steps + 1):
        at = k / approach_steps
        ax = start_mouse_x + (sx - start_mouse_x) * at
        ay = start_mouse_y + (sy - start_mouse_y) * at
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": ax, "y": ay, "buttons": 0})
        await asyncio.sleep(0.015)
    await asyncio.sleep(random.uniform(0.10, 0.18))

    # Mouse pressed with proper buttons state
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": sx, "y": sy, "button": "left", "buttons": 1, "clickCount": 1})
    await asyncio.sleep(random.uniform(0.08, 0.14))

    # Ballistic overshoot (capped so it never hits the right wall)
    overshoot_amt = random.uniform(5.0, 9.0)
    if dist + overshoot_amt > max_track:
        overshoot_amt = max(0.5, max_track - dist)
    over = min(max_track, dist + overshoot_amt)

    n = 42
    for i in range(1, n + 1):
        t = i / n
        ease = 1.0 - (1.0 - t) ** 3
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": sx + over * ease,
            "y": sy + np.sin(t * 5.0) * 1.2,
            "button": "left",
            "buttons": 1
        })
        await asyncio.sleep(0.011 + (i % 4) * 0.004)

    # Correction phase: drift smoothly back to target
    cn = 10
    for j in range(1, cn + 1):
        t = j / cn
        cur = over + (dist - over) * t
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": sx + cur,
            "y": sy + random.uniform(-0.6, 0.6),
            "button": "left",
            "buttons": 1
        })
        await asyncio.sleep(0.02 + random.uniform(0.0, 0.015))

    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": sx + dist, "y": sy, "button": "left", "buttons": 1})
    await asyncio.sleep(0.16 + random.uniform(0.0, 0.10))
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": sx + dist, "y": sy, "button": "left", "buttons": 0, "clickCount": 1})

async def solve_qwen_registration(url: str, email: str, mail=None, timeout_s: int = 180, max_attempts: int = 10) -> dict:
    """End-to-end Aliyun Captcha solver & in-browser account registration."""
    t_start = time.monotonic()
    browser = await launch_async(
        headless=True,
        humanize=False,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )

    try:
        ctx = await browser.new_context()
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)

        # Block purely cosmetic fonts and media to save bandwidth and CPU
        async def route_filter(route):
            req = route.request
            rt = req.resource_type
            u = req.url
            if rt in ("font", "media"):
                return await route.abort()
            if "google-analytics" in u or "doubleclick" in u:
                return await route.abort()
            return await route.continue_()

        await page.route("**/*", route_filter)
        await page.add_init_script(_HOOK_JS)

        images: dict[str, bytes] = {}
        verify_success: dict = {"v": None}
        attempt_failed: dict = {"v": False}
        otp_sent: dict = {"v": False}
        auth_token: dict = {"v": None}

        async def on_response(resp):
            u = resp.url
            if "otp/email/verify" in u or "auths/token" in u:
                ct = resp.headers.get("content-type", "")
                if "application/json" in ct:
                    try:
                        txt = await resp.text()
                        j = json.loads(txt) if txt.strip().startswith("{") else None
                        if j:
                            t = (j.get("token") or j.get("access_token") or
                                 j.get("data", {}).get("token") or j.get("data", {}).get("access_token"))
                            if t:
                                auth_token["v"] = t
                    except Exception:
                        pass
                return
            if "otp/email/request" in u:
                ct = resp.headers.get("content-type", "")
                if "application/json" in ct:
                    try:
                        txt = await resp.text()
                        if '"success":true' in txt.replace(" ", ""):
                            otp_sent["v"] = True
                    except Exception:
                        pass
                return
            if "static-captcha" in u and u.endswith(".png"):
                try:
                    images[u.rsplit("/", 1)[-1]] = await resp.body()
                except Exception:
                    pass
                return
            if "captcha-open" in u or "aliyuncs" in u:
                try:
                    txt = await resp.text()
                    j = json.loads(txt) if txt.strip().startswith("{") else None
                    if j and "Result" in j and isinstance(j["Result"], dict):
                        res_dict = j["Result"]
                        if res_dict.get("VerifyResult") is False:
                            attempt_failed["v"] = True
                        elif res_dict.get("VerifyResult") is True:
                            verify_success["v"] = res_dict
                except Exception:
                    pass

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        # Fast page load: wait until domcontentloaded
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Directly wait for email input
        email_loc = page.locator('input[name="email"], input[placeholder*="mail" i], input[type=email]').first
        await email_loc.wait_for(state="visible", timeout=20000)
        await email_loc.fill(email)

        # Remove splash screen if present to prevent pointer interception
        try:
            await page.evaluate("() => { const s = document.getElementById('splash-screen'); if (s) s.remove(); }")
        except Exception:
            pass
        btn = page.locator('button.qwenchat-email-otp-panel-button').first
        await btn.click(force=True)
        print(f"  ⚡ Form submitted in {round(time.monotonic() - t_start, 1)}s. Waiting for puzzle...")

        # Solve loop
        for attempt in range(1, max_attempts + 1):
            attempt_failed["v"] = False

            # Wait for slider handle to mount (fast polling 100ms)
            slider = None
            for _ in range(100):
                if time.monotonic() - t_start > timeout_s:
                    return {"solved": False, "error": f"timed out after {timeout_s}s"}
                slider = await page.evaluate(_FIND_SLIDER_JS)
                if slider:
                    break
                await page.wait_for_timeout(100)

            if not slider:
                continue

            # Intercept challenge images (fast polling 80ms)
            back_b = None
            piece_b = None
            for _ in range(60):
                if not back_b:
                    for b_name in ("back.png", "bg.png"):
                        if b_name in images:
                            back_b = images.pop(b_name)
                            break
                if not piece_b:
                    for s_name in ("shadow.png", "bitwise_and_result.png"):
                        if s_name in images:
                            piece_b = images.pop(s_name)
                            break
                if back_b and piece_b:
                    break

                # Fallback to DOM elements
                dom_imgs = await page.evaluate("""() => {
                    const bg = document.getElementById('aliyunCaptcha-img');
                    const puzzle = document.getElementById('aliyunCaptcha-puzzle');
                    if (!bg || !puzzle) return null;
                    const mk = (img) => {
                        if (!img || !img.naturalWidth || img.naturalWidth < 10) return null;
                        try {
                            const c = document.createElement('canvas');
                            c.width = img.naturalWidth;
                            c.height = img.naturalHeight;
                            c.getContext('2d').drawImage(img, 0, 0);
                            return c.toDataURL('image/png');
                        } catch(e) { return null; }
                    };
                    const b = mk(bg);
                    const p = mk(puzzle);
                    return (b && p) ? { bg: b, puzzle: p } : null;
                }""")
                if dom_imgs:
                    _b64 = lambda d: base64.b64decode(d.split(",")[-1])
                    back_b = _b64(dom_imgs["bg"])
                    piece_b = _b64(dom_imgs["puzzle"])
                    break
                await page.wait_for_timeout(80)

            if not back_b or not piece_b:
                await page.wait_for_timeout(200)
                continue

            # Detect puzzle gap and calculate target drag distance
            g = detect_gap_x(back_b, piece_b)
            geo = None
            for _ in range(20):
                geo = await page.evaluate("""() => {
                    const bg = document.getElementById('aliyunCaptcha-img');
                    if (!bg) return null;
                    const r = bg.getBoundingClientRect();
                    const w = r.width;
                    const natW = bg.naturalWidth;
                    if (w > 50 && natW > 50) {
                        return { w, natW };
                    }
                    return null;
                }""")
                if geo:
                    break
                await page.wait_for_timeout(80)

            if not geo:
                geo = {"w": 300, "natW": 296}

            scale = geo["w"] / geo["natW"]
            if scale < 0.8 or scale > 1.3:
                scale = 300.0 / 296.0

            target = g["gap_x"] * scale
            dist = float(_invert(target))
            if dist < 10.0:
                dist = 50.0

            print(f"  ⚡ [Attempt #{attempt}] Gap: {g.get('gap_x')}px ({g.get('method')}) -> Target drag: {dist:.1f}px")

            # Natural human reaction pause to locate puzzle hole
            await asyncio.sleep(random.uniform(1.2, 1.8))

            await _human_drag(cdp, slider, dist)

            # Check verdict (fast polling 100ms)
            R = None
            for _ in range(60):
                if otp_sent.get("v"):
                    if not mail:
                        print(f"  ✔ [Attempt #{attempt}] OTP email dispatched instantly by Qwen!")
                        return {
                            "solved": True,
                            "verify_code": "T001",
                            "method": "real-page",
                            "attempts": attempt,
                            "elapsed": round(time.monotonic() - t_start, 1)
                        }
                    else:
                        R = "OTP_DISPATCHED"
                        break
                if verify_success.get("v"):
                    R = verify_success["v"]
                    break
                caps = await page.evaluate("""() => {
                    const s = window.__cb_success;
                    const b = (window.__btoa_hits || []).slice(-1);
                    const otp = document.querySelectorAll('input.ant-otp-input, .qwenchat-verification-code-input-cell').length;
                    return { s, b: (b && b.length) ? b[0] : null, otp };
                }""")
                if caps.get("s"):
                    R = caps["s"]
                    break
                if caps.get("b"):
                    R = caps["b"]
                    break
                if caps.get("otp") and caps["otp"] >= 4:
                    R = "OTP_DISPATCHED"
                    break
                if attempt_failed.get("v"):
                    break
                await page.wait_for_timeout(100)

            if R or otp_sent.get("v"):
                if mail:
                    print(f"  ✔ [Attempt #{attempt}] Captcha passed, waiting for OTP screen...")
                    for _ in range(40):
                        has_otp = await page.evaluate("""() => {
                            const body = document.body ? document.body.innerText : '';
                            const hasText = body.includes('Check your inbox') || body.includes('sent a verification code to');
                            const otpCells = document.querySelectorAll('input.ant-otp-input, .qwenchat-verification-code-input-cell, input[autocomplete="one-time-code"]').length;
                            return hasText || otpCells >= 4;
                        }""")
                        if has_otp:
                            break
                        await page.wait_for_timeout(250)

                    print("  📬 Waiting for 6-digit OTP code in Mazdoor inbox...")
                    loop = asyncio.get_running_loop()
                    otp_code = await loop.run_in_executor(None, lambda: mail.get_otp_code(timeout=75))
                    if otp_code:
                        print(f"  ✔ OTP Code Received: {otp_code}. Entering into Qwen inputs...")
                        otp_cell = page.locator('input.ant-otp-input, .qwenchat-verification-code-input-cell, input[autocomplete="one-time-code"]').first
                        await otp_cell.click()
                        await page.keyboard.type(str(otp_code), delay=60)

                        # Wait for auth token
                        for _ in range(50):
                            if auth_token.get("v"):
                                break
                            try:
                                ls_token = await page.evaluate("() => localStorage.getItem('token') || localStorage.getItem('access_token')")
                                if ls_token:
                                    auth_token["v"] = ls_token
                                    break
                            except Exception:
                                pass
                            await page.wait_for_timeout(200)

                        cookies_list = await ctx.cookies()
                        cookies_dict = {c["name"]: c["value"] for c in cookies_list}

                        if auth_token.get("v"):
                            return {
                                "solved": True,
                                "otp_code": otp_code,
                                "token": auth_token.get("v"),
                                "cookies": cookies_dict,
                                "verify_code": "T001",
                                "method": "real-page",
                                "attempts": attempt,
                                "elapsed": round(time.monotonic() - t_start, 1)
                            }
                        else:
                            return {
                                "solved": False,
                                "error": "OTP entered but no auth token intercepted",
                                "elapsed": round(time.monotonic() - t_start, 1)
                            }
                    else:
                        return {
                            "solved": False,
                            "error": "Timed out waiting for OTP email",
                            "elapsed": round(time.monotonic() - t_start, 1)
                        }

                return {
                    "solved": True,
                    "verify_code": "T001",
                    "method": "real-page",
                    "attempts": attempt,
                    "elapsed": round(time.monotonic() - t_start, 1)
                }

                # If OTP did not confirm, check for error toast on page
                toast_err = await page.evaluate("""() => {
                    const el = document.querySelector('.ant-message, [class*="toast"], [role="alert"]');
                    return el ? el.innerText : '';
                }""")
                log.warning(f"Aliyun passed on attempt {attempt} but OTP screen did not mount. Alert: {toast_err}")

            images.clear()
            await page.evaluate("""() => {
                const btn = document.getElementById('aliyunCaptcha-btn-refresh');
                if (btn) btn.click();
            }""")
            await page.wait_for_timeout(random.randint(2200, 3000))

        return {
            "solved": False,
            "error": f"no R in {max_attempts} attempts",
            "elapsed": round(time.monotonic() - t_start, 1)
        }

    finally:
        try:
            await browser.close()
        except Exception:
            pass
