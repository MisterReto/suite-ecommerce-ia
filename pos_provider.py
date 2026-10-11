"""POS contracts are inert until explicitly configured; no destructive stubs."""

from typing import Protocol


class POSProvider(Protocol):
    def items(self): ...
    def variants(self): ...
    def categories(self): ...
    def stores(self): ...
    def inventory(self, store_id): ...
    def receipts(self): ...


class LoyverseProvider:
    supported_events = {"inventory_levels.update", "items.update", "receipts.update"}

    def __init__(self, token=None):
        self.token = token

    def _list(self, entity, **params):
        if not self.token:
            raise RuntimeError("Loyverse aún no está conectado.")
        from loyverse_client import LoyverseClient

        return LoyverseClient(self.token).list(entity, **params)

    def items(self):
        return self._list("items")

    def variants(self):
        return [v for item in self.items() for v in item.get("variants", [])]

    def categories(self):
        return self._list("categories")

    def stores(self):
        return self._list("stores")

    def inventory(self, store_id):
        return self._list("inventory", store_ids=store_id)

    def receipts(self):
        return self._list("receipts")
