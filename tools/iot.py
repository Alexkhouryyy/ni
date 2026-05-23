"""IoT channel — inbound webhook triggers and outbound HA service calls.

Inbound:
  HA automations POST to /iot/webhook (wired in dashboard/server.py).
  Each event dispatches an agent turn on a per-entity channel so memory
  is isolated per device/entity.

Outbound:
  iot_call_service(domain, service, data) — calls HA REST API directly.
  iot_get_state(entity_id) — reads current state from HA.
  iot_notify(target, message) — sends a notification via HA notify service.

Setup:
  1. Set IOT_HA_URL and IOT_HA_TOKEN in .env.
  2. Optionally set IOT_WEBHOOK_SECRET for HMAC-signed inbound triggers.
  3. Add entity IDs to IOT_TRIGGER_ALLOWED_ENTITIES to allow inbound events.
  4. In HA: create an automation that posts JSON to https://your-host/iot/webhook.
"""
from typing import Callable, Optional

import config

_agent_run_fn: Optional[Callable] = None


def set_agent_run_fn(fn: Callable) -> None:
    global _agent_run_fn
    _agent_run_fn = fn


def is_configured() -> bool:
    return bool(config.IOT_HA_URL and config.IOT_HA_TOKEN)


def _allowed_entities() -> set[str]:
    return set(getattr(config, "IOT_TRIGGER_ALLOWED_ENTITIES", []) or [])


def _is_allowed(entity_id: str) -> bool:
    allowed = _allowed_entities()
    return not allowed or entity_id in allowed


def dispatch_inbound(payload: dict) -> Optional[str]:
    """Process one inbound IoT webhook payload. Returns agent reply or None."""
    from agent.iot import is_enabled
    if not is_enabled():
        return None

    entity_id: str = payload.get("entity_id", "")
    event_type: str = payload.get("event", payload.get("trigger", "event"))
    state: str = payload.get("state", "")
    friendly: str = payload.get("friendly_name", entity_id)

    if not entity_id:
        return None

    if not _is_allowed(entity_id):
        print(f"[IoT] Blocked inbound from non-allowlisted entity: {entity_id}")
        return None

    if _agent_run_fn is None:
        print("[IoT] Agent not wired yet — inbound event dropped.")
        return None

    description = friendly or entity_id
    text = f"[IoT event] {description} triggered '{event_type}'"
    if state:
        text += f" (state: {state})"

    try:
        reply = _agent_run_fn(text, channel_id=f"iot:{entity_id}")
    except Exception as e:
        reply = f"Agent error: {e}"

    return reply


def iot_call_service(domain: str, service: str, data: dict | None = None) -> str:
    """Call a Home Assistant service. Returns result summary."""
    from agent.iot import is_enabled, ha_call_service
    if not is_enabled():
        return "[IoT is disabled]"
    result = ha_call_service(domain, service, data or {})
    if "error" in result:
        return f"[IoT] Service call failed: {result['error']}"
    return f"[IoT] {domain}.{service} called successfully."


def iot_get_state(entity_id: str) -> str:
    """Get the current state of a HA entity. Returns state string."""
    from agent.iot import is_enabled, ha_get_state
    if not is_enabled():
        return "[IoT is disabled]"
    result = ha_get_state(entity_id)
    if "error" in result:
        return f"[IoT] get_state failed: {result['error']}"
    state = result.get("state", "unknown")
    attrs = result.get("attributes", {})
    friendly = attrs.get("friendly_name", entity_id)
    return f"{friendly} ({entity_id}): {state}"


def iot_notify(target: str, message: str, title: str = "") -> str:
    """Send a notification via HA notify service."""
    from agent.iot import is_enabled, ha_notify
    if not is_enabled():
        return "[IoT is disabled]"
    result = ha_notify(target, message, title)
    if "error" in result:
        return f"[IoT] notify failed: {result['error']}"
    return f"[IoT] Notification sent via notify.{target}."
