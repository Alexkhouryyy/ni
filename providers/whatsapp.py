"""
JARVIS WhatsApp Reservation Provider.

Drafts a wa.me deep-link so the user just taps Send.
No Playwright required — simpler and safer (user retains explicit send control).
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from providers.base import ReservationDraft, ReservationProvider, ReservationResult

log = logging.getLogger("jarvis.providers.whatsapp")

_MESSAGE_TEMPLATE = (
    "Hi, I'd like to book a table for {party} on {pretty_time} "
    "under the name {user_name}. Please confirm. Thanks!"
)


def _pretty_time(iso_time: str) -> str:
    """Convert ISO 8601 or a free-form string to a readable format."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_time)
        return dt.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
    except Exception:
        return iso_time  # Return as-is if parsing fails


class WhatsAppReservationProvider(ReservationProvider):
    """Opens a wa.me deep-link with a pre-filled reservation message."""

    name = "whatsapp"

    async def draft(self, restaurant: str, party_size: int,
                    reservation_time: str, phone: str = "",
                    email: str = "", user_name: str = "sir") -> ReservationDraft:
        """Build the WhatsApp message and deep-link URL."""
        pretty = _pretty_time(reservation_time)
        message = _MESSAGE_TEMPLATE.format(
            party=party_size,
            pretty_time=pretty,
            user_name=user_name,
        )

        # Normalise phone: strip spaces/dashes, ensure leading +
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if clean_phone and not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone

        deep_link = f"https://wa.me/{clean_phone.lstrip('+')}?text={quote(message)}"

        log.info(f"WhatsApp draft for {restaurant}: {party_size} pax @ {pretty}")
        return ReservationDraft(
            provider="whatsapp",
            restaurant=restaurant,
            phone=clean_phone,
            party_size=party_size,
            reservation_time=reservation_time,
            drafted_message=message,
            deep_link=deep_link,
        )

    async def send(self, draft: ReservationDraft) -> ReservationResult:
        """Open the deep-link in the default browser.

        The user taps Send themselves — JARVIS never sends WhatsApp messages
        autonomously.
        """
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                import os
                os.startfile(draft.deep_link)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", draft.deep_link])
            else:
                subprocess.Popen(["xdg-open", draft.deep_link])

            log.info(f"Opened WhatsApp deep-link for {draft.restaurant}")
            return ReservationResult(
                success=True,
                status="draft",
                message=(
                    f"WhatsApp is open with the booking drafted, sir. "
                    f"Tap send when you're ready."
                ),
            )
        except Exception as e:
            log.error(f"Failed to open WhatsApp deep-link: {e}")
            return ReservationResult(
                success=False,
                status="failed",
                message=f"Couldn't open WhatsApp, sir: {e}",
            )
