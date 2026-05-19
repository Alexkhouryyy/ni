"""Real browser automation via Playwright.

The agent can drive a Chromium browser: navigate, click, type, submit forms,
screenshot, extract content, run JS. A single persistent browser instance is
kept alive across tool calls.
"""
import asyncio
import base64
import threading
from typing import Optional

_pw = None
_browser = None
_context = None
_page = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None


def _ensure_loop():
    """Run a dedicated event loop in a background thread."""
    global _loop, _loop_thread
    if _loop is not None and _loop.is_running():
        return _loop
    _loop = asyncio.new_event_loop()

    def runner():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _loop_thread = threading.Thread(target=runner, daemon=True, name="PlaywrightLoop")
    _loop_thread.start()
    return _loop


def _run(coro):
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)


async def _ensure_browser(headless: bool = False):
    global _pw, _browser, _context, _page
    if _page is not None:
        return _page
    from playwright.async_api import async_playwright
    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(headless=headless, args=["--no-sandbox"])
    _context = await _browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    )
    _page = await _context.new_page()
    return _page


async def _shutdown():
    global _pw, _browser, _context, _page
    if _page:
        try: await _page.close()
        except Exception: pass
    if _context:
        try: await _context.close()
        except Exception: pass
    if _browser:
        try: await _browser.close()
        except Exception: pass
    if _pw:
        try: await _pw.stop()
        except Exception: pass
    _pw = _browser = _context = _page = None


# === Sync tool wrappers ===

def goto(url: str, headless: bool = False) -> str:
    async def _go():
        page = await _ensure_browser(headless=headless)
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await page.title()
        return f"Loaded {url}\nTitle: {title}\nStatus: {resp.status if resp else 'n/a'}"
    return _run(_go())


def click(selector: str) -> str:
    async def _c():
        page = await _ensure_browser()
        await page.click(selector, timeout=10000)
        return f"Clicked: {selector}"
    return _run(_c())


def fill(selector: str, text: str) -> str:
    async def _f():
        page = await _ensure_browser()
        await page.fill(selector, text, timeout=10000)
        return f"Filled {selector!r} with: {text!r}"
    return _run(_f())


def press(key: str) -> str:
    async def _p():
        page = await _ensure_browser()
        await page.keyboard.press(key)
        return f"Pressed: {key}"
    return _run(_p())


def get_text(selector: str = "body") -> str:
    async def _t():
        page = await _ensure_browser()
        el = page.locator(selector).first
        text = await el.inner_text(timeout=10000)
        return text[:6000] + ("..." if len(text) > 6000 else "")
    return _run(_t())


def get_html(selector: str = "body") -> str:
    async def _h():
        page = await _ensure_browser()
        el = page.locator(selector).first
        html = await el.inner_html(timeout=10000)
        return html[:6000] + ("..." if len(html) > 6000 else "")
    return _run(_h())


def screenshot() -> str:
    """Returns base64-encoded PNG screenshot of the current browser viewport."""
    async def _s():
        page = await _ensure_browser()
        png = await page.screenshot(full_page=False)
        return base64.standard_b64encode(png).decode("utf-8")
    return _run(_s())


def evaluate(js: str) -> str:
    async def _e():
        page = await _ensure_browser()
        result = await page.evaluate(js)
        return str(result)[:6000]
    return _run(_e())


def current_url() -> str:
    async def _u():
        page = await _ensure_browser()
        return page.url
    return _run(_u())


def close():
    try:
        _run(_shutdown())
    except Exception:
        pass
    return "Browser closed"
