"""
JARVIS Provider Abstraction — base ABCs and shared dataclasses.

Every food-ordering and reservation provider implements these interfaces.
The orchestrator talks only to these ABCs — adding a new provider (DoorDash,
OpenTable, etc.) never requires touching orders.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Shared data models
# ---------------------------------------------------------------------------

@dataclass
class Address:
    label: str          # 'home', 'office'
    full_address: str
    phone: str = ""
    region: str = "me"  # 'me' (Middle East) | 'us'


@dataclass
class Restaurant:
    id: str             # provider-specific ID / slug
    name: str
    cuisine: str = ""
    rating: float = 0.0
    eta_minutes: int = 0
    min_order: float = 0.0
    currency: str = "USD"
    phone: str = ""


@dataclass
class MenuItem:
    id: str
    name: str
    price: float
    currency: str = "USD"
    description: str = ""
    available: bool = True


@dataclass
class Menu:
    restaurant_id: str
    restaurant_name: str
    items: list[MenuItem] = field(default_factory=list)


@dataclass
class OrderItem:
    name: str
    quantity: int = 1
    size: str = ""               # 'small', 'medium', 'large'
    modifiers: list[str] = field(default_factory=list)
    unit_price: float = 0.0
    confidence: float = 1.0      # transcription confidence (0-1)


@dataclass
class CartDraft:
    provider: str
    restaurant_id: str
    restaurant_name: str
    items: list[OrderItem]
    address: Address
    subtotal: float = 0.0
    fees: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    eta_minutes: int = 0
    payment_method: str = "cash_on_delivery"
    notes: str = ""


@dataclass
class OrderResult:
    success: bool
    provider_order_id: str = ""
    status: str = ""             # 'submitted' | 'aborted' | 'failed'
    eta_minutes: int = 0
    total: float = 0.0
    currency: str = "USD"
    aborted_reason: str = ""     # 'card_required' | 'selector:<name>' | 'user_declined'
    message: str = ""            # human-readable outcome for TTS


@dataclass
class ReservationDraft:
    provider: str
    restaurant: str
    phone: str
    party_size: int
    reservation_time: str        # ISO 8601
    drafted_message: str = ""
    deep_link: str = ""


@dataclass
class ReservationResult:
    success: bool
    reservation_id: int = 0
    status: str = "draft"
    message: str = ""


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------

class OrderProvider(ABC):
    """Interface every food-delivery provider must implement."""

    name: str   # 'toters' | 'doordash' | 'ubereats'
    region: str  # 'me' | 'us' | 'global'

    @abstractmethod
    async def search_restaurants(self, query: str, address: Address) -> list[Restaurant]:
        """Return restaurants matching *query* near *address*."""

    @abstractmethod
    async def get_menu(self, restaurant_id: str) -> Menu:
        """Return the menu for a restaurant."""

    @abstractmethod
    async def build_cart(self, restaurant_id: str, items: list[OrderItem],
                         address: Address, notes: str = "") -> CartDraft:
        """Add items to cart and return pricing + ETA without placing the order."""

    @abstractmethod
    async def submit_order(self, cart: CartDraft) -> OrderResult:
        """Place the order (cash-on-delivery only). Never charge a card."""

    async def close(self):
        """Release browser / session resources. Override if needed."""


class ReservationProvider(ABC):
    """Interface every reservation channel must implement."""

    name: str   # 'whatsapp' | 'opentable' | 'email'

    @abstractmethod
    async def draft(self, restaurant: str, party_size: int,
                    reservation_time: str, phone: str = "",
                    email: str = "", user_name: str = "sir") -> ReservationDraft:
        """Compose the reservation message / booking without sending."""

    @abstractmethod
    async def send(self, draft: ReservationDraft) -> ReservationResult:
        """Send / open the reservation (open deep link, submit form, etc.)."""
