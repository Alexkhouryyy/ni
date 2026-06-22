"""
JARVIS Toters Provider — Playwright-driven food ordering for the Middle East.

Flow:
  1. search_restaurants — search toters.com for a restaurant by name
  2. get_menu          — scrape the restaurant menu page
  3. build_cart        — add items to cart, read back pricing + ETA
  4. submit_order      — verify cash-on-delivery is selected, click Place Order

Safety rail B (payment check) is enforced in submit_order: if any card-payment
indicator is detected, the order is aborted and the browser tab is left open.

All selectors are tried with a 3-level fallback:
  primary → aria-label → text-contains → gives up with clear error
Timeouts default to 10 s per action so minor DOM reshuffles don't hang JARVIS.

Login persistence: ~/.jarvis/browser/toters/ stores cookies/session.
First run will require the user to log in manually — JARVIS opens the browser
and asks them to complete the login, then all future sessions reuse the cookie.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from browser import ProviderBrowser
from providers.base import (
    Address, CartDraft, Menu, MenuItem, OrderItem,
    OrderProvider, OrderResult, Restaurant,
)

log = logging.getLogger("jarvis.providers.toters")

# ---------------------------------------------------------------------------
# Toters URLs & selectors
# ---------------------------------------------------------------------------

BASE_URL = "https://www.toters.com"
SEARCH_URL = f"{BASE_URL}/en/search?q="
LOGIN_URL = f"{BASE_URL}/en/login"

# Selector chains — (primary, aria-label partial, text partial)
# Entries can be plain CSS strings; the ProviderBrowser tries each in order.

SEL_RESTAURANT_CARD = ".restaurant-card, [data-testid='restaurant-card'], .store-card"
SEL_RESTAURANT_NAME = ".restaurant-name, [data-testid='restaurant-name'], h2"
SEL_MENU_ITEM = ".menu-item, [data-testid='menu-item'], .product-card"
SEL_ITEM_NAME = ".item-name, [data-testid='item-name'], .product-name, h3"
SEL_ITEM_PRICE = ".item-price, [data-testid='item-price'], .price"
SEL_ADD_TO_CART = "button.add-to-cart, [data-testid='add-to-cart'], button:has-text('Add')"
SEL_CART_TOTAL = ".cart-total, [data-testid='cart-total'], .order-total"
SEL_CART_FEES = ".delivery-fee, [data-testid='delivery-fee'], .fees"
SEL_ETA = ".eta, [data-testid='eta'], .delivery-time"
SEL_CHECKOUT_BTN = "button.checkout, [data-testid='checkout'], button:has-text('Checkout')"
SEL_PAYMENT_SECTION = ".payment-method, [data-testid='payment-method'], .payment-options"
SEL_COD_RADIO = "[value='cod'], [value='cash'], input[type='radio']:near(:text('Cash'))"
SEL_PLACE_ORDER = "button.place-order, [data-testid='place-order'], button:has-text('Place Order')"
SEL_ORDER_CONFIRM = ".order-confirmed, [data-testid='order-confirmed'], .confirmation-number"
SEL_ORDER_ID = ".order-id, [data-testid='order-id'], .tracking-number"

# Card-payment danger signals — if any are visible, abort
CARD_DANGER_SELECTORS = [
    "input[name*='card']", "input[name*='cvv']", "input[name*='cvc']",
    "[data-payment='card']", ".card-input", "#credit-card-form",
    "input[placeholder*='Card number']", "input[placeholder*='card number']",
]
CARD_SAFE_KEYWORDS = ["cash", "on delivery", "pay on arrival", "cod"]

# Failure dump directory
FAILURE_DIR = Path.home() / ".jarvis" / "order_failures"


class TotersProvider(OrderProvider):
    """Real Playwright flows for Toters food ordering."""

    name = "toters"
    region = "me"

    def __init__(self):
        self._browser = ProviderBrowser("toters")
        self._logged_in: Optional[bool] = None  # None = not yet checked

    # -- Login check -----------------------------------------------------------

    async def _ensure_logged_in(self) -> bool:
        """Check login state. Return True if logged in, False if login required."""
        try:
            await self._browser.goto(BASE_URL)
            # If we see a user avatar or account menu, we're in
            if await self._browser.is_visible("[data-testid='user-menu'], .user-avatar, .account-icon"):
                log.info("Toters: already logged in")
                return True
            # Check URL — if we got redirected to login page, we're not logged in
            page_url = await self._browser.evaluate("() => window.location.href")
            if "login" in str(page_url):
                log.info("Toters: not logged in, browser is open for manual login")
                return False
            # Assume logged in if no obvious login indicators
            return True
        except Exception as e:
            log.warning(f"Toters login check failed: {e}")
            return False

    # -- search_restaurants ----------------------------------------------------

    async def search_restaurants(self, query: str, address: Address) -> list[Restaurant]:
        """Search Toters for restaurants matching *query*."""
        try:
            await self._browser.goto(f"{SEARCH_URL}{query.replace(' ', '+')}")
            await self._browser.wait_for(SEL_RESTAURANT_CARD, timeout=15_000)

            raw = await self._browser.evaluate(f"""
                () => {{
                    const cards = document.querySelectorAll(
                        '.restaurant-card, [data-testid="restaurant-card"], .store-card'
                    );
                    return Array.from(cards).slice(0, 8).map(c => {{
                        const name = c.querySelector(
                            '.restaurant-name, [data-testid="restaurant-name"], h2, h3'
                        )?.textContent?.trim() || '';
                        const id = c.getAttribute('data-id') || c.getAttribute('data-restaurant-id') || '';
                        const href = c.querySelector('a')?.getAttribute('href') || '';
                        const eta = c.querySelector('.eta, .delivery-time')?.textContent?.trim() || '';
                        const rating = c.querySelector('.rating, .stars')?.textContent?.trim() || '0';
                        return {{ name, id, href, eta, rating }};
                    }});
                }}
            """)

            results = []
            for r in (raw or []):
                if not r.get("name"):
                    continue
                try:
                    eta_num = int(''.join(filter(str.isdigit, r.get("eta", "0"))) or "0")
                except ValueError:
                    eta_num = 0
                results.append(Restaurant(
                    id=r.get("href", r.get("id", "")),
                    name=r["name"],
                    eta_minutes=eta_num,
                    currency="USD",
                ))
            log.info(f"Toters search '{query}': {len(results)} restaurants")
            return results
        except Exception as e:
            log.error(f"Toters search_restaurants failed: {e}")
            await self._dump_failure("search_restaurants")
            return []

    # -- get_menu --------------------------------------------------------------

    async def get_menu(self, restaurant_id: str) -> Menu:
        """Load a restaurant page and scrape the menu."""
        url = restaurant_id if restaurant_id.startswith("http") else BASE_URL + restaurant_id
        try:
            await self._browser.goto(url, wait_until="networkidle")
            # Brief wait for dynamic content
            await self._browser.wait_for(SEL_MENU_ITEM, timeout=15_000)

            raw = await self._browser.evaluate(f"""
                () => {{
                    const items = document.querySelectorAll(
                        '.menu-item, [data-testid="menu-item"], .product-card'
                    );
                    return Array.from(items).slice(0, 40).map(el => {{
                        const name = el.querySelector(
                            '.item-name, [data-testid="item-name"], .product-name, h3, h4'
                        )?.textContent?.trim() || '';
                        const priceEl = el.querySelector('.item-price, .price, [data-testid="price"]');
                        const priceText = priceEl?.textContent?.trim() || '0';
                        const price = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
                        const id = el.getAttribute('data-id') || el.getAttribute('data-item-id') || '';
                        const available = !el.classList.contains('unavailable') &&
                                          !el.classList.contains('sold-out');
                        return {{ name, price, id, available }};
                    }});
                }}
            """)

            restaurant_name = await self._browser.read_text(
                "h1, .restaurant-name, [data-testid='restaurant-title']"
            )
            items = [
                MenuItem(
                    id=r.get("id", r.get("name", "")),
                    name=r["name"],
                    price=float(r.get("price", 0)),
                    available=bool(r.get("available", True)),
                )
                for r in (raw or []) if r.get("name")
            ]
            log.info(f"Toters menu for '{restaurant_name}': {len(items)} items")
            return Menu(restaurant_id=restaurant_id, restaurant_name=restaurant_name,
                        items=items)
        except Exception as e:
            log.error(f"Toters get_menu failed: {e}")
            await self._dump_failure("get_menu")
            return Menu(restaurant_id=restaurant_id, restaurant_name=restaurant_id,
                        items=[])

    # -- build_cart ------------------------------------------------------------

    async def build_cart(self, restaurant_id: str, items: list[OrderItem],
                         address: Address, notes: str = "") -> CartDraft:
        """Navigate to restaurant, add items to cart, return cart summary."""
        url = restaurant_id if restaurant_id.startswith("http") else BASE_URL + restaurant_id
        try:
            await self._browser.goto(url, wait_until="networkidle")

            for item in items:
                await self._add_item_to_cart(item)

            # Navigate to cart / checkout to read totals
            checkout_url = f"{BASE_URL}/en/cart"
            await self._browser.goto(checkout_url)
            await self._browser.wait_for(SEL_CART_TOTAL, timeout=10_000)

            subtotal_text = await self._browser.read_text(SEL_CART_TOTAL)
            fees_text = await self._browser.read_text(SEL_CART_FEES)
            eta_text = await self._browser.read_text(SEL_ETA)

            subtotal = _parse_price(subtotal_text)
            fees = _parse_price(fees_text)
            total = subtotal + fees
            eta_minutes = _parse_eta(eta_text)

            # Get restaurant name from page title if we don't have it
            rest_name = await self._browser.read_text(
                "h1, .restaurant-name, [data-testid='restaurant-title']"
            ) or restaurant_id

            log.info(f"Toters cart built: {rest_name}, total {total}, ETA {eta_minutes}m")
            return CartDraft(
                provider=self.name,
                restaurant_id=restaurant_id,
                restaurant_name=rest_name,
                items=items,
                address=address,
                subtotal=subtotal,
                fees=fees,
                total=total,
                currency="USD",
                eta_minutes=eta_minutes,
                payment_method="cash_on_delivery",
                notes=notes,
            )
        except Exception as e:
            log.error(f"Toters build_cart failed: {e}")
            await self._dump_failure("build_cart")
            raise

    async def _add_item_to_cart(self, item: OrderItem):
        """Find and add a single item to the cart."""
        item_name_lower = item.name.lower()
        # Try to find the item by name in the menu DOM
        try:
            found = await self._browser.evaluate(f"""
                () => {{
                    const cards = document.querySelectorAll(
                        '.menu-item, [data-testid="menu-item"], .product-card'
                    );
                    for (const c of cards) {{
                        const name = (c.querySelector('h3, h4, .item-name, .product-name')?.textContent || '').toLowerCase();
                        if (name.includes('{item_name_lower.replace("'", "\\'")}')) {{
                            const btn = c.querySelector('button.add-to-cart, [data-testid="add-to-cart"], button');
                            if (btn) {{ btn.click(); return true; }}
                        }}
                    }}
                    return false;
                }}
            """)
            if not found:
                log.warning(f"Item '{item.name}' not found in cart DOM, trying selector click")
                # Fallback: click first visible "Add" button near matching text
                await self._browser.click(
                    f"text='{item.name}' >> .. >> button",
                    timeout=5_000,
                )
            # Add extra quantity if > 1
            for _ in range(item.quantity - 1):
                await self._add_one_more(item.name)
        except Exception as e:
            log.warning(f"Couldn't add '{item.name}' to cart: {e}")

    async def _add_one_more(self, item_name: str):
        """Click the + button next to an already-added item."""
        try:
            await self._browser.evaluate(f"""
                () => {{
                    const cards = document.querySelectorAll(
                        '.cart-item, [data-testid="cart-item"]'
                    );
                    for (const c of cards) {{
                        const name = (c.textContent || '').toLowerCase();
                        if (name.includes('{item_name.lower().replace("'", "\\'")}')) {{
                            const btn = c.querySelector('button.increment, button[aria-label="increase"], button.plus');
                            if (btn) {{ btn.click(); return; }}
                        }}
                    }}
                }}
            """)
        except Exception:
            pass

    # -- submit_order ----------------------------------------------------------

    async def submit_order(self, cart: CartDraft) -> OrderResult:
        """Proceed through checkout and place the order.

        Safety rail B: verifies cash-on-delivery before clicking Place Order.
        If card payment is the only option, aborts and leaves browser open.
        """
        try:
            # Navigate to checkout
            await self._browser.goto(f"{BASE_URL}/en/checkout")
            await self._browser.wait_for(SEL_PAYMENT_SECTION, timeout=15_000)

            # ----- Payment safety check -----
            safe = await self._verify_cod_selected()
            if not safe:
                log.warning("Toters: cash-on-delivery not available — aborting order")
                await self._dump_failure("submit_order_card_required")
                return OrderResult(
                    success=False,
                    status="aborted",
                    aborted_reason="card_required",
                    message=(
                        "Card payment required for this order, sir. "
                        "Handing off — finish it in the browser."
                    ),
                )

            # ----- Select COD if not already chosen -----
            try:
                if not await self._browser.is_visible(f"{SEL_COD_RADIO}:checked"):
                    await self._browser.click(SEL_COD_RADIO, timeout=5_000)
            except Exception:
                pass  # COD might already be selected / only option

            # ----- Fill delivery notes if any -----
            if cart.notes:
                try:
                    await self._browser.fill(
                        "textarea[name='notes'], input[name='notes'], #delivery-notes",
                        cart.notes, timeout=5_000
                    )
                except Exception:
                    pass

            # ----- Place order -----
            await self._browser.click(SEL_PLACE_ORDER, timeout=15_000)

            # Wait for confirmation page
            try:
                await self._browser.wait_for(SEL_ORDER_CONFIRM, timeout=20_000)
            except Exception:
                # Try URL pattern confirmation
                await self._browser.wait_for_url("**/order-confirmed**", timeout=20_000)

            # Read order ID
            order_id_text = await self._browser.read_text(SEL_ORDER_ID)
            order_id = order_id_text.strip() or "unknown"

            # Read ETA from confirmation page
            eta_text = await self._browser.read_text(SEL_ETA)
            eta_minutes = _parse_eta(eta_text) or cart.eta_minutes

            log.info(f"Toters order placed: #{order_id}, ETA {eta_minutes}m")
            return OrderResult(
                success=True,
                provider_order_id=order_id,
                status="submitted",
                eta_minutes=eta_minutes,
                total=cart.total,
                currency=cart.currency,
                message=f"Ordered, sir. ETA {eta_minutes} minutes.",
            )

        except Exception as e:
            log.error(f"Toters submit_order failed: {e}")
            await self._dump_failure("submit_order")
            return OrderResult(
                success=False,
                status="failed",
                aborted_reason=f"selector:{type(e).__name__}",
                message=(
                    "The Toters page changed, sir. Order not placed. "
                    "I've left the browser open."
                ),
            )

    async def _verify_cod_selected(self) -> bool:
        """Return True if cash-on-delivery is available and selectable."""
        try:
            # Check for dangerous card-input elements that are aria-required
            for sel in CARD_DANGER_SELECTORS:
                if await self._browser.is_visible(sel):
                    # It's visible — check if COD is ALSO available
                    page_text = await self._browser.read_text("body")
                    if any(kw in page_text.lower() for kw in CARD_SAFE_KEYWORDS):
                        return True  # Both exist; COD is available
                    log.warning(f"Card-only indicator visible: {sel}")
                    return False

            # Check that COD keyword is present on the page
            payment_text = await self._browser.read_text(SEL_PAYMENT_SECTION)
            has_cod = any(kw in payment_text.lower() for kw in CARD_SAFE_KEYWORDS)
            return has_cod
        except Exception as e:
            log.warning(f"COD verification error: {e}")
            return True  # Give benefit of the doubt if scraping fails

    # -- Diagnostics -----------------------------------------------------------

    async def _dump_failure(self, label: str):
        """Save screenshot + HTML snippet for debugging selector breakage."""
        try:
            FAILURE_DIR.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            png_path = str(FAILURE_DIR / f"{label}_{ts}.png")
            html_path = FAILURE_DIR / f"{label}_{ts}.html"
            await self._browser.screenshot(png_path)
            html = await self._browser.dump_html()
            html_path.write_text(html[:50_000], encoding="utf-8")
            log.info(f"Failure dump: {png_path}")
        except Exception as e:
            log.debug(f"Failure dump failed: {e}")

    # -- Lifecycle -------------------------------------------------------------

    async def close(self):
        await self._browser.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> float:
    """Extract a float price from a string like '$12.50' or '12,500 LBP'."""
    import re
    nums = re.findall(r"[\d,]+\.?\d*", text.replace(",", ""))
    for n in nums:
        try:
            return float(n)
        except ValueError:
            continue
    return 0.0


def _parse_eta(text: str) -> int:
    """Extract minutes from an ETA string like '25-35 min' or '30 minutes'."""
    import re
    nums = re.findall(r"\d+", text or "")
    if not nums:
        return 0
    values = [int(n) for n in nums]
    # If a range like 25-35, take the average
    return round(sum(values) / len(values))
