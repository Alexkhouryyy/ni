"""Wire every messaging channel's inbound dispatch to the live agent.

Each channel module (phone, telegram, discord, slack, whatsapp, signal) exposes
a `set_agent_run_fn(fn)` hook. Its inbound webhook handler calls that fn to get
a reply. Without it, inbound messages get "Agent not ready yet."

This helper centralizes the wiring so both entry points — `main.py` (voice/text)
and `app/resident.py` (always-on daemon) — share one implementation. Previously
only `main.py` wired the channels, so the resident daemon silently ignored every
inbound message.
"""
from tools import phone, telegram, discord, slack, whatsapp, signal
import config


def wire_channels(agent) -> None:
    """Point every channel's inbound dispatch at the given agent."""
    def run(text: str, *, channel_id: str | None = None) -> str:
        try:
            return agent.run(
                text,
                include_screenshot=False,
                use_thinking=False,
                channel_id=channel_id,
            )
        except Exception as e:
            return f"Agent error: {e}"

    for mod in (phone, telegram, discord, slack, whatsapp, signal):
        mod.set_agent_run_fn(run)

    # IoT is wired only when explicitly enabled — it can actuate physical devices.
    if config.IOT_ENABLED:
        from agent import iot as iot_state
        from tools import iot as iot_tools
        iot_state.init_db()
        iot_tools.set_agent_run_fn(run)
        if not config.IOT_WEBHOOK_SECRET:
            print("[IoT] WARNING: IOT_WEBHOOK_SECRET not set — inbound webhooks are unauthenticated.")
