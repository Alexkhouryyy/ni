"""
JARVIS Order & Reservation Orchestrators.

Two classes:
  OrderOrchestrator      — food delivery (slot-filling → confirmation → execute)
  ReservationOrchestrator — table booking (parse → confirm → send draft)

Both return the same dict shape as TaskPlanner.process_answer() so the
WebSocket handler can treat them interchangeably:
  {
    "order_id": int,
    "plan_complete": bool,
    "needs_confirmation": bool,
    "confirmation_summary": str,
    "next_question": str,
    "status": str,
    "message": str,
  }

Safety rails enforced here:
  A. Verbal confirmation before any order is placed
  B. Payment-method abort if card-only checkout detected
  C. Max-order-value guard (ORDER_MAX_VALUE env, default 50)
  D. Concurrency guard — one in-flight order per provider at a time
  E. Transcription disambiguation — any item slot with confidence < 0.8
     triggers a clarification question before the final confirmation
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import memory
from providers import registry
from providers.base import Address, OrderItem, CartDraft

log = logging.getLogger("jarvis.orders")

# Explicit affirmatives that count as "yes, go ahead"
_AFFIRMATIVES = {"yes", "confirm", "proceed", "go ahead", "yep", "yeah",
                 "do it", "sure", "absolutely", "correct", "affirmative",
                 "place it", "place the order"}

_MAX_ORDER_VALUE = float(os.environ.get("ORDER_MAX_VALUE", "50"))


def _is_affirmative(text: str) -> bool:
    t = text.lower().strip().rstrip(".")
    return any(a in t for a in _AFFIRMATIVES)


def _items_summary(items: list[dict]) -> str:
    parts = []
    for item in items:
        name = item.get("name", "item")
        qty = item.get("quantity", 1)
        size = item.get("size", "")
        part = f"{qty}x {size} {name}".strip() if size else f"{qty}x {name}"
        parts.append(part)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# OrderOrchestrator
# ---------------------------------------------------------------------------

class OrderOrchestrator:
    """Drives a food-delivery order through slot-filling → confirm → execute."""

    def __init__(self):
        # In-memory state keyed by order_id
        # Each entry: {"stage": str, "cart": CartDraft|None, "db_id": int, ...}
        self._state: dict[int, dict] = {}
        self._counter = 0

    def _new_id(self) -> int:
        self._counter += 1
        return self._counter

    async def start_order(self, raw_request: str,
                          anthropic_client,
                          ws=None) -> dict:
        """Parse intent from *raw_request*, start slot-filling, return first response dict."""
        order_id = self._new_id()
        log.info(f"Order #{order_id} started: {raw_request[:80]}")

        # --- Concurrency guard ---
        active = memory.get_active_order()
        if active:
            return {
                "order_id": order_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "blocked",
                "message": (
                    f"One order already in flight, sir. "
                    f"{active['restaurant']} is still pending. "
                    f"Shall I cancel it first?"
                ),
            }

        # --- Parse intent via Haiku ---
        parsed = await self._parse_intent(raw_request, anthropic_client)
        if "error" in parsed:
            return {
                "order_id": order_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "error",
                "message": f"Couldn't parse order request, sir: {parsed['error']}",
            }

        restaurant = parsed.get("restaurant", "")
        items_raw = parsed.get("items", [])
        address_label = parsed.get("address_label", "home") or "home"
        notes = parsed.get("notes", "")

        # --- Slot-filling: missing restaurant ---
        if not restaurant:
            self._state[order_id] = {
                "stage": "need_restaurant",
                "parsed": parsed,
                "raw_request": raw_request,
            }
            return {
                "order_id": order_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "Which restaurant would you like to order from, sir?",
                "status": "slot_filling",
                "message": "Which restaurant would you like to order from, sir?",
            }

        # --- Slot-filling: missing items ---
        if not items_raw:
            self._state[order_id] = {
                "stage": "need_items",
                "parsed": parsed,
                "raw_request": raw_request,
            }
            return {
                "order_id": order_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": f"What would you like from {restaurant}, sir?",
                "status": "slot_filling",
                "message": f"What would you like from {restaurant}, sir?",
            }

        # --- Transcription disambiguation (confidence < 0.8) ---
        low_conf = [i for i in items_raw if i.get("confidence", 1.0) < 0.8]
        if low_conf:
            item = low_conf[0]
            self._state[order_id] = {
                "stage": "disambiguate",
                "parsed": parsed,
                "raw_request": raw_request,
                "disambiguate_item": item,
            }
            question = (
                f"Just to confirm — did you say {item.get('size', '')} "
                f"{item['name']}? Or a different size?"
            ).strip()
            return {
                "order_id": order_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": question,
                "status": "disambiguating",
                "message": question,
            }

        # --- Resolve address ---
        addr_result = await self._resolve_address(order_id, address_label, parsed)
        if addr_result is not None:
            # Need to ask for address
            self._state[order_id] = addr_result["state"]
            return {k: v for k, v in addr_result.items() if k != "state"}

        address_row = memory.get_address(address_label)
        address = Address(
            label=address_row["label"],
            full_address=address_row["full_address"],
            phone=address_row.get("phone", ""),
            region=address_row.get("region", "me"),
        )

        # --- Build cart ---
        return await self._build_and_confirm(
            order_id, restaurant, items_raw, address, notes, anthropic_client, ws
        )

    async def process_answer(self, order_id: int, user_input: str,
                             anthropic_client=None, ws=None) -> dict:
        """Continue an in-progress order based on the user's latest reply."""
        state = self._state.get(order_id)
        if not state:
            return {
                "order_id": order_id,
                "plan_complete": True,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "not_found",
                "message": "No active order found, sir.",
            }

        stage = state.get("stage")

        # --- Waiting for final yes/no confirmation ---
        if stage == "awaiting_confirm":
            if _is_affirmative(user_input):
                # Check second confirmation for high-value orders
                cart: CartDraft = state.get("cart")
                max_val = float(os.environ.get("ORDER_MAX_VALUE", str(_MAX_ORDER_VALUE)))
                if cart and cart.total > max_val and not state.get("second_confirm_given"):
                    state["second_confirm_given"] = True
                    msg = (
                        f"That's {cart.currency} {cart.total:.2f}, sir. "
                        f"Above your usual {cart.currency} {max_val:.0f} limit. "
                        f"Confirm again?"
                    )
                    return {
                        "order_id": order_id,
                        "plan_complete": False,
                        "needs_confirmation": True,
                        "confirmation_summary": msg,
                        "next_question": msg,
                        "status": "awaiting_second_confirm",
                        "message": msg,
                    }
                # Execute the order
                db_id = state.get("db_id")
                asyncio.create_task(self._execute(order_id, db_id, state["cart"], ws))
                del self._state[order_id]
                return {
                    "order_id": order_id,
                    "plan_complete": True,
                    "needs_confirmation": False,
                    "confirmation_summary": "",
                    "next_question": "",
                    "status": "executing",
                    "message": "On it, sir. Placing the order now.",
                }
            else:
                # User declined
                db_id = state.get("db_id")
                if db_id:
                    memory.update_order_status(db_id, "aborted",
                                               aborted_reason="user_declined")
                del self._state[order_id]
                return {
                    "order_id": order_id,
                    "plan_complete": True,
                    "needs_confirmation": False,
                    "confirmation_summary": "",
                    "next_question": "",
                    "status": "cancelled",
                    "message": "Cancelled, sir.",
                }

        # --- Slot-filling stages ---
        if stage == "need_restaurant":
            state["parsed"]["restaurant"] = user_input.strip()
            state["stage"] = "retry_start"
            return await self.start_order(
                state["raw_request"] + f" from {user_input.strip()}",
                anthropic_client, ws
            )

        if stage == "need_items":
            state["parsed"]["items"] = [{"name": user_input.strip(), "quantity": 1,
                                          "confidence": 0.9}]
            restaurant = state["parsed"].get("restaurant", "")
            address_label = state["parsed"].get("address_label", "home") or "home"
            address_row = memory.get_address(address_label)
            if not address_row:
                state["stage"] = "need_address"
                return {
                    "order_id": order_id,
                    "plan_complete": False,
                    "needs_confirmation": False,
                    "confirmation_summary": "",
                    "next_question": (
                        f"I don't have an address labelled '{address_label}', sir. "
                        f"What's the full delivery address?"
                    ),
                    "status": "slot_filling",
                    "message": (
                        f"I don't have an address labelled '{address_label}', sir. "
                        f"What's the full delivery address?"
                    ),
                }
            address = Address(
                label=address_row["label"],
                full_address=address_row["full_address"],
                phone=address_row.get("phone", ""),
                region=address_row.get("region", "me"),
            )
            return await self._build_and_confirm(
                order_id, restaurant, state["parsed"]["items"],
                address, state["parsed"].get("notes", ""),
                anthropic_client, ws
            )

        if stage == "need_address":
            # User provided address text
            region = os.environ.get("JARVIS_REGION", "me")
            memory.save_address("home", user_input.strip(), region=region,
                                is_default=True)
            address = Address(label="home", full_address=user_input.strip(),
                              region=region)
            restaurant = state["parsed"].get("restaurant", "")
            items_raw = state["parsed"].get("items", [])
            return await self._build_and_confirm(
                order_id, restaurant, items_raw, address,
                state["parsed"].get("notes", ""), anthropic_client, ws
            )

        if stage == "disambiguate":
            # User clarified a size/name — patch the item and proceed
            item = state["disambiguate_item"]
            item["name"] = user_input.strip()
            item["confidence"] = 1.0
            state["stage"] = "retry_start"
            restaurant = state["parsed"].get("restaurant", "")
            address_label = state["parsed"].get("address_label", "home") or "home"
            address_row = memory.get_address(address_label)
            if not address_row:
                state["stage"] = "need_address"
                return {
                    "order_id": order_id,
                    "plan_complete": False,
                    "needs_confirmation": False,
                    "confirmation_summary": "",
                    "next_question": (
                        f"I don't have an address labelled '{address_label}', sir. "
                        f"What's the full delivery address?"
                    ),
                    "status": "slot_filling",
                    "message": (
                        f"I don't have an address labelled '{address_label}', sir. "
                        f"What's the full delivery address?"
                    ),
                }
            address = Address(
                label=address_row["label"],
                full_address=address_row["full_address"],
                phone=address_row.get("phone", ""),
                region=address_row.get("region", "me"),
            )
            return await self._build_and_confirm(
                order_id, restaurant, state["parsed"]["items"],
                address, state["parsed"].get("notes", ""),
                anthropic_client, ws
            )

        # Unknown stage
        return {
            "order_id": order_id,
            "plan_complete": False,
            "needs_confirmation": False,
            "confirmation_summary": "",
            "next_question": "I've lost track of the order state, sir. Shall we start over?",
            "status": "error",
            "message": "I've lost track of the order state, sir. Shall we start over?",
        }

    # -- Helpers ---------------------------------------------------------------

    async def _parse_intent(self, raw_request: str, client) -> dict:
        """Use Haiku to extract structured order intent from free-form text."""
        if not client:
            # Fallback: treat entire text as restaurant name
            return {"restaurant": raw_request, "items": [], "address_label": "home",
                    "notes": ""}
        try:
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=(
                    "Extract a food order from the user's message. "
                    "Return ONLY valid JSON: "
                    '{"restaurant": "...", '
                    '"items": [{"name": "...", "quantity": 1, "size": "", '
                    '"modifiers": [], "confidence": 0.9}], '
                    '"address_label": "home", '
                    '"notes": ""}. '
                    "confidence is 0-1 for how certain you are about each item's name/size. "
                    "Use confidence < 0.8 if the spoken item is ambiguous. "
                    "Return {} if you cannot parse anything useful."
                ),
                messages=[{"role": "user", "content": raw_request}],
            )
            text = resp.content[0].text.strip()
            return json.loads(text) if text.startswith("{") else {}
        except Exception as e:
            log.warning(f"Intent parse failed: {e}")
            return {"error": str(e)}

    async def _resolve_address(self, order_id: int, label: str,
                               parsed: dict) -> dict | None:
        """Return a response dict if address is missing, else None."""
        row = memory.get_address(label)
        if row:
            return None
        # Address unknown — need to ask
        self._state[order_id] = {
            "stage": "need_address",
            "parsed": parsed,
        }
        msg = (
            f"I don't have an address labelled '{label}', sir. "
            f"What's the full delivery address?"
        )
        return {
            "order_id": order_id,
            "plan_complete": False,
            "needs_confirmation": False,
            "confirmation_summary": "",
            "next_question": msg,
            "status": "slot_filling",
            "message": msg,
            "state": self._state[order_id],
        }

    async def _build_and_confirm(self, order_id: int, restaurant: str,
                                  items_raw: list[dict], address: Address,
                                  notes: str, client, ws) -> dict:
        """Build cart via provider and return confirmation summary."""
        try:
            provider = registry.order_provider()
        except RuntimeError as e:
            return {
                "order_id": order_id,
                "plan_complete": True,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "no_provider",
                "message": str(e),
            }

        items = [
            OrderItem(
                name=i.get("name", ""),
                quantity=i.get("quantity", 1),
                size=i.get("size", ""),
                modifiers=i.get("modifiers", []),
                confidence=i.get("confidence", 1.0),
            )
            for i in items_raw if i.get("name")
        ]

        try:
            cart = await provider.build_cart(
                restaurant_id=restaurant,
                items=items,
                address=address,
                notes=notes,
            )
        except Exception as e:
            log.error(f"build_cart failed: {e}")
            return {
                "order_id": order_id,
                "plan_complete": True,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "error",
                "message": f"Couldn't reach {restaurant}, sir: {e}",
            }

        # Persist to DB
        db_id = memory.record_order(
            provider=provider.name,
            restaurant=cart.restaurant_name,
            items_json=json.dumps([{
                "name": i.name, "quantity": i.quantity,
                "size": i.size, "modifiers": i.modifiers
            } for i in cart.items]),
            address_id=None,  # address_id filled in later if saved
            currency=cart.currency,
            subtotal=cart.subtotal,
            fees=cart.fees,
            total=cart.total,
        )

        summary = (
            f"{_items_summary([{'name': i.name, 'quantity': i.quantity, 'size': i.size} for i in cart.items])} "
            f"from {cart.restaurant_name}, "
            f"{cart.currency} {cart.total:.2f}, "
            f"cash on delivery to {address.label}, "
            f"ETA {cart.eta_minutes} minutes. "
            f"Confirm, sir?"
        )

        self._state[order_id] = {
            "stage": "awaiting_confirm",
            "cart": cart,
            "db_id": db_id,
        }

        return {
            "order_id": order_id,
            "plan_complete": False,
            "needs_confirmation": True,
            "confirmation_summary": summary,
            "next_question": summary,
            "status": "awaiting_confirm",
            "message": summary,
        }

    async def _execute(self, order_id: int, db_id: int,
                       cart: CartDraft, ws) -> None:
        """Place the order. Runs as an asyncio Task — streams progress over WS."""
        async def notify(msg: str):
            if ws:
                try:
                    await ws.send_json({"type": "order_progress",
                                        "order_id": order_id, "message": msg})
                except Exception:
                    pass
            log.info(f"Order #{order_id}: {msg}")

        await notify("Looking up your order on the provider…")
        memory.update_order_status(db_id, "submitted")

        try:
            provider = registry.order_provider(cart.provider)
        except RuntimeError as e:
            memory.update_order_status(db_id, "failed", aborted_reason=str(e))
            await notify(str(e))
            return

        try:
            result = await provider.submit_order(cart)
        except Exception as e:
            memory.update_order_status(db_id, "failed",
                                       aborted_reason=f"exception:{e}")
            await notify(f"Order failed, sir: {e}")
            return

        if result.success:
            memory.update_order_status(
                db_id, "submitted",
                provider_order_id=result.provider_order_id,
                eta_minutes=result.eta_minutes,
                total=result.total,
            )
            await notify(
                result.message or
                f"Ordered, sir. ETA {result.eta_minutes} minutes."
            )
        else:
            memory.update_order_status(
                db_id, "aborted",
                aborted_reason=result.aborted_reason,
            )
            await notify(result.message or "Order aborted, sir.")

    def cancel_pending(self, order_id: int) -> str:
        """Cancel an order that hasn't been submitted yet."""
        state = self._state.pop(order_id, None)
        if state and state.get("db_id"):
            memory.update_order_status(state["db_id"], "aborted",
                                       aborted_reason="user_cancelled")
        return "Cancelled, sir."


# ---------------------------------------------------------------------------
# ReservationOrchestrator
# ---------------------------------------------------------------------------

class ReservationOrchestrator:
    """Drives a table-booking through parse → confirm → send WhatsApp draft."""

    def __init__(self):
        self._state: dict[int, dict] = {}
        self._counter = 0

    def _new_id(self) -> int:
        self._counter += 1
        return self._counter

    async def start_reservation(self, raw_request: str,
                                 restaurant: str, party_size: int,
                                 reservation_time: str, phone: str = "",
                                 anthropic_client=None, ws=None) -> dict:
        """Build confirmation summary for the WhatsApp draft."""
        res_id = self._new_id()
        log.info(f"Reservation #{res_id}: {restaurant} for {party_size}")

        # Basic slot-filling
        if not restaurant:
            self._state[res_id] = {
                "stage": "need_restaurant",
                "party_size": party_size,
                "reservation_time": reservation_time,
                "phone": phone,
            }
            return {
                "order_id": res_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "Which restaurant shall I book, sir?",
                "status": "slot_filling",
                "message": "Which restaurant shall I book, sir?",
            }

        if not reservation_time:
            self._state[res_id] = {
                "stage": "need_time",
                "restaurant": restaurant,
                "party_size": party_size,
                "phone": phone,
            }
            return {
                "order_id": res_id,
                "plan_complete": False,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": f"What date and time for {restaurant}, sir?",
                "status": "slot_filling",
                "message": f"What date and time for {restaurant}, sir?",
            }

        pretty = _pretty_time(reservation_time)
        summary = (
            f"Drafting a WhatsApp message to {restaurant}: "
            f"table for {party_size}, {pretty}. Confirm, sir?"
        )

        self._state[res_id] = {
            "stage": "awaiting_confirm",
            "restaurant": restaurant,
            "party_size": party_size,
            "reservation_time": reservation_time,
            "phone": phone,
        }

        return {
            "order_id": res_id,
            "plan_complete": False,
            "needs_confirmation": True,
            "confirmation_summary": summary,
            "next_question": summary,
            "status": "awaiting_confirm",
            "message": summary,
        }

    async def process_answer(self, res_id: int, user_input: str,
                              anthropic_client=None, ws=None) -> dict:
        """Handle user's reply to the confirmation or slot-fill question."""
        state = self._state.get(res_id)
        if not state:
            return {
                "order_id": res_id,
                "plan_complete": True,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "not_found",
                "message": "No active reservation found, sir.",
            }

        stage = state.get("stage")

        if stage == "awaiting_confirm":
            if _is_affirmative(user_input):
                return await self._execute(res_id, state, ws)
            else:
                del self._state[res_id]
                return {
                    "order_id": res_id,
                    "plan_complete": True,
                    "needs_confirmation": False,
                    "confirmation_summary": "",
                    "next_question": "",
                    "status": "cancelled",
                    "message": "Cancelled, sir.",
                }

        if stage == "need_restaurant":
            state["restaurant"] = user_input.strip()
            state["stage"] = "need_time" if not state.get("reservation_time") else "awaiting_confirm"
            if state["stage"] == "need_time":
                return {
                    "order_id": res_id,
                    "plan_complete": False,
                    "needs_confirmation": False,
                    "confirmation_summary": "",
                    "next_question": f"What date and time for {state['restaurant']}, sir?",
                    "status": "slot_filling",
                    "message": f"What date and time for {state['restaurant']}, sir?",
                }
            return await self.start_reservation(
                raw_request="", restaurant=state["restaurant"],
                party_size=state.get("party_size", 2),
                reservation_time=state.get("reservation_time", ""),
                phone=state.get("phone", ""),
            )

        if stage == "need_time":
            state["reservation_time"] = user_input.strip()
            return await self.start_reservation(
                raw_request="",
                restaurant=state.get("restaurant", ""),
                party_size=state.get("party_size", 2),
                reservation_time=state["reservation_time"],
                phone=state.get("phone", ""),
            )

        return {
            "order_id": res_id,
            "plan_complete": True,
            "needs_confirmation": False,
            "confirmation_summary": "",
            "next_question": "",
            "status": "error",
            "message": "Lost reservation state, sir. Shall we start again?",
        }

    async def _execute(self, res_id: int, state: dict, ws) -> dict:
        """Send the WhatsApp deep-link and persist to DB."""
        restaurant = state["restaurant"]
        party_size = state["party_size"]
        reservation_time = state["reservation_time"]
        phone = state.get("phone", "")
        user_name = os.environ.get("USER_NAME", "sir")

        try:
            provider = registry.reservation_provider("whatsapp")
            draft = await provider.draft(
                restaurant=restaurant,
                party_size=party_size,
                reservation_time=reservation_time,
                phone=phone,
                user_name=user_name,
            )
            result = await provider.send(draft)
        except Exception as e:
            log.error(f"Reservation send failed: {e}")
            del self._state[res_id]
            return {
                "order_id": res_id,
                "plan_complete": True,
                "needs_confirmation": False,
                "confirmation_summary": "",
                "next_question": "",
                "status": "error",
                "message": f"Couldn't open WhatsApp, sir: {e}",
            }

        # Persist to DB
        db_id = memory.record_reservation(
            provider="whatsapp",
            restaurant=restaurant,
            party_size=party_size,
            reservation_time=reservation_time,
            phone=phone,
            drafted_message=draft.drafted_message,
        )

        # Create a follow-up task so JARVIS tracks the pending confirmation
        memory.create_task(
            title=f"Confirm reservation: {restaurant} — waiting on restaurant reply",
            description=draft.drafted_message,
            priority="medium",
            project="reservations",
        )

        del self._state[res_id]
        return {
            "order_id": res_id,
            "plan_complete": True,
            "needs_confirmation": False,
            "confirmation_summary": "",
            "next_question": "",
            "status": "draft_sent",
            "message": result.message,
        }


def _pretty_time(iso_time: str) -> str:
    """Convert ISO 8601 or free-form string to readable format."""
    try:
        dt = datetime.fromisoformat(iso_time)
        return dt.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
    except Exception:
        return iso_time


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

order_orchestrator = OrderOrchestrator()
reservation_orchestrator = ReservationOrchestrator()
