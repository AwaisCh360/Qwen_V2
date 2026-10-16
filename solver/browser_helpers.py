"""Browser helpers for selector resolution and pre-action execution."""
import asyncio
import logging
import re

log = logging.getLogger("solver.browser")

async def resolve_selector(page, selector: str, timeout: int = 10000):
    """Resolve selector to Playwright locator (CSS, XPath, Text)."""
    if selector.startswith("//") or selector.startswith("(//"):
        return page.locator(f"xpath={selector}")
    if selector.startswith("text="):
        return page.get_by_text(selector[5:], exact=False)
    if selector.startswith("regex="):
        return page.locator(f"text=/{selector[6:]}/")
    return page.locator(selector)

async def run_pre_actions(page, actions: list):
    """Execute pre-actions (fill email, click send OTP)."""
    for i, action in enumerate(actions):
        atype = action.get("type", "")
        selector = action.get("selector", "")
        value = action.get("value", "")
        timeout = action.get("timeout", 10000)
        optional = bool(action.get("optional"))
        attempts = 2 if atype in ("click", "fill") else 1

        for attempt in range(1, attempts + 1):
            try:
                if atype == "click":
                    loc = await resolve_selector(page, selector, timeout)
                    await loc.click(timeout=timeout)
                elif atype == "fill":
                    loc = await resolve_selector(page, selector, timeout)
                    await loc.fill(value, timeout=timeout)
                elif atype == "wait":
                    await asyncio.sleep(float(value or 1))
                break
            except Exception as e:
                if attempt < attempts:
                    await page.wait_for_timeout(1500)
                    continue
                if not optional:
                    raise
