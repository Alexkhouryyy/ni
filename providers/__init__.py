"""
JARVIS Provider Registry — central lookup for order + reservation providers.

Region comes from the JARVIS_REGION env var:
  auto  — pick the best provider for the detected region (default)
  me    — Middle East: Toters
  us    — USA: DoorDash / Uber Eats (V2 stubs for now)

Usage:
    from providers import registry
    provider = registry.order_provider()        # → TotersProvider or stub
    rp = registry.reservation_provider("whatsapp")
"""

from __future__ import annotations

import logging
import os

from providers.base import OrderProvider, ReservationProvider

log = logging.getLogger("jarvis.providers")


class ProviderRegistry:
    """Singleton registry. Lazily instantiates providers on first use."""

    def __init__(self):
        self._order_providers: dict[str, OrderProvider] = {}
        self._reservation_providers: dict[str, ReservationProvider] = {}
        self._region = os.environ.get("JARVIS_REGION", "auto").lower()
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True

        # --- Order providers ---
        if os.environ.get("TOTERS_ENABLED", "true").lower() in ("true", "1", "yes"):
            try:
                from providers.toters import TotersProvider
                self._order_providers["toters"] = TotersProvider()
                log.info("TotersProvider registered")
            except Exception as e:
                log.warning(f"Could not load TotersProvider: {e}")

        # V2 stubs — will raise NotImplementedError if called
        try:
            from providers.doordash import DoorDashProvider
            self._order_providers["doordash"] = DoorDashProvider()
        except Exception:
            pass

        try:
            from providers.ubereats import UberEatsProvider
            self._order_providers["ubereats"] = UberEatsProvider()
        except Exception:
            pass

        # --- Reservation providers ---
        try:
            from providers.whatsapp import WhatsAppReservationProvider
            self._reservation_providers["whatsapp"] = WhatsAppReservationProvider()
            log.info("WhatsAppReservationProvider registered")
        except Exception as e:
            log.warning(f"Could not load WhatsAppReservationProvider: {e}")

        try:
            from providers.opentable import OpenTableProvider
            self._reservation_providers["opentable"] = OpenTableProvider()
        except Exception:
            pass

        try:
            from providers.email_reservation import EmailReservationProvider
            self._reservation_providers["email"] = EmailReservationProvider()
        except Exception:
            pass

    def order_provider(self, name: str = None) -> OrderProvider:
        """Return the best available order provider for the current region.

        Pass *name* to request a specific provider.
        Raises RuntimeError if no suitable provider is available.
        """
        self._load()

        if name:
            p = self._order_providers.get(name)
            if p is None:
                raise RuntimeError(f"Order provider '{name}' is not registered.")
            return p

        # Auto-select by region
        region = self._region
        if region in ("auto", "me"):
            if "toters" in self._order_providers:
                return self._order_providers["toters"]
        if region in ("auto", "us"):
            for n in ("doordash", "ubereats"):
                if n in self._order_providers:
                    return self._order_providers[n]

        raise RuntimeError(
            "No order provider available for the current region. "
            "Food ordering is only wired up for Toters right now, sir."
        )

    def reservation_provider(self, name: str = "whatsapp") -> ReservationProvider:
        """Return a reservation provider by name (default: whatsapp)."""
        self._load()
        p = self._reservation_providers.get(name)
        if p is None:
            raise RuntimeError(f"Reservation provider '{name}' is not registered.")
        return p

    def available_order_providers(self) -> list[str]:
        self._load()
        return list(self._order_providers.keys())

    def available_reservation_providers(self) -> list[str]:
        self._load()
        return list(self._reservation_providers.keys())

    async def close_all(self):
        """Shut down all provider browser sessions."""
        self._load()
        for p in self._order_providers.values():
            try:
                await p.close()
            except Exception:
                pass


# Module-level singleton
registry = ProviderRegistry()
