"""DoorDash provider — V2 stub."""
from providers.base import Address, CartDraft, Menu, OrderItem, OrderProvider, OrderResult, Restaurant


class DoorDashProvider(OrderProvider):
    name = "doordash"
    region = "us"

    async def search_restaurants(self, query: str, address: Address) -> list[Restaurant]:
        raise NotImplementedError("DoorDash provider coming in v2")

    async def get_menu(self, restaurant_id: str) -> Menu:
        raise NotImplementedError("DoorDash provider coming in v2")

    async def build_cart(self, restaurant_id: str, items: list[OrderItem],
                         address: Address, notes: str = "") -> CartDraft:
        raise NotImplementedError("DoorDash provider coming in v2")

    async def submit_order(self, cart: CartDraft) -> OrderResult:
        raise NotImplementedError("DoorDash provider coming in v2")
