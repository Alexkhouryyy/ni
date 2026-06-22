"""OpenTable reservation provider — V2 stub."""
from providers.base import ReservationDraft, ReservationProvider, ReservationResult


class OpenTableProvider(ReservationProvider):
    name = "opentable"

    async def draft(self, restaurant: str, party_size: int,
                    reservation_time: str, phone: str = "",
                    email: str = "", user_name: str = "sir") -> ReservationDraft:
        raise NotImplementedError("OpenTable provider coming in v2")

    async def send(self, draft: ReservationDraft) -> ReservationResult:
        raise NotImplementedError("OpenTable provider coming in v2")
