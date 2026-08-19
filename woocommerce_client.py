"""Cliente mínimo y seguro para la REST API de WooCommerce.

No contiene secretos. Las credenciales se leen de variables de entorno de Render.
Las escrituras están deshabilitadas salvo que WC_WRITE_ENABLED=true.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WooCommerceError(RuntimeError):
    pass


@dataclass(frozen=True)
class WooCommerceConfig:
    base_url: str
    consumer_key: str = ""
    consumer_secret: str = ""
    write_enabled: bool = False
    timeout: int = 20

    @classmethod
    def from_env(cls) -> "WooCommerceConfig":
        base_url = os.getenv("WC_URL", "https://rincon.creandotusite.com").rstrip("/")
        return cls(
            base_url=base_url,
            consumer_key=os.getenv("WC_CONSUMER_KEY", "").strip(),
            consumer_secret=os.getenv("WC_CONSUMER_SECRET", "").strip(),
            write_enabled=os.getenv("WC_WRITE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
            timeout=int(os.getenv("WC_TIMEOUT", "20")),
        )

    @property
    def configured(self) -> bool:
        return bool(self.consumer_key and self.consumer_secret)


class WooCommerceClient:
    def __init__(self, config: WooCommerceConfig | None = None):
        self.config = config or WooCommerceConfig.from_env()

    def _auth_header(self) -> str:
        if not self.config.configured:
            raise WooCommerceError(
                "Faltan WC_CONSUMER_KEY y WC_CONSUMER_SECRET en las variables de entorno."
            )
        raw = f"{self.config.consumer_key}:{self.config.consumer_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def request(self, method: str, endpoint: str, *, params: dict[str, Any] | None = None,
                payload: dict[str, Any] | None = None) -> Any:
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "DELETE"}:
            raise ValueError(f"Método no soportado: {method}")
        if method != "GET" and not self.config.write_enabled:
            raise WooCommerceError(
                "Escrituras WooCommerce deshabilitadas. Define WC_WRITE_ENABLED=true solo después de validar el preview."
            )

        url = f"{self.config.base_url}/wp-json/wc/v3/{endpoint.lstrip('/')}"
        if params:
            url += "?" + urlencode(params, doseq=True)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": self._auth_header(),
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "RinconDeAsia-SuiteEcommerceIA/1.0",
            },
        )
        try:
            with urlopen(req, timeout=self.config.timeout) as response:
                data = response.read().decode("utf-8")
                return json.loads(data) if data else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WooCommerceError(f"WooCommerce HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise WooCommerceError(f"No se pudo conectar con WooCommerce: {exc.reason}") from exc

    def list_products(self, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return self.request("GET", "products", params={"page": page, "per_page": per_page}) or []

    def list_variations(self, product_id: int, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return self.request(
            "GET", f"products/{int(product_id)}/variations",
            params={"page": page, "per_page": per_page},
        ) or []

    def list_setting_groups(self) -> list[dict[str, Any]]:
        return self.request("GET", "settings") or []

    def list_settings(self, group_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"settings/{group_id}") or []

    def get_setting(self, group_id: str, setting_id: str) -> dict[str, Any]:
        return self.request("GET", f"settings/{group_id}/{setting_id}") or {}

    def _paginate(self, getter, *, per_page: int = 100, max_pages: int = 100):
        rows = []
        for page in range(1, max_pages + 1):
            batch = getter(page=page, per_page=per_page)
            rows.extend(batch)
            if len(batch) < per_page:
                break
        return rows

    def list_all_products(self) -> list[dict[str, Any]]:
        return self._paginate(self.list_products)

    def list_all_variations(self, product_id: int) -> list[dict[str, Any]]:
        return self._paginate(lambda **kw: self.list_variations(product_id, **kw))

    def catalog_by_sku(self, *, include_variations: bool = True):
        """Devuelve (índice SKU->producto, duplicados SKU->[productos])."""
        index: dict[str, dict[str, Any]] = {}
        duplicates: dict[str, list[dict[str, Any]]] = {}

        def add(row: dict[str, Any], entity_type: str, parent_id: int | None = None):
            sku = str(row.get("sku", "") or "").strip()
            if not sku:
                return
            item = dict(row)
            item["_entity_type"] = entity_type
            item["_parent_product_id"] = parent_id
            if sku in index:
                duplicates.setdefault(sku, [index[sku]]).append(item)
            else:
                index[sku] = item

        productos = self.list_all_products()
        for product in productos:
            add(product, "product")
            if include_variations and product.get("type") == "variable":
                for variation in self.list_all_variations(product["id"]):
                    add(variation, "variation", parent_id=product["id"])
        return index, duplicates

    def find_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        rows = self.request("GET", "products", params={"sku": sku, "per_page": 100})
        for row in rows or []:
            if str(row.get("sku", "")).strip() == str(sku).strip():
                return row
        return None

    def update_stock(self, product_id: int, stock_quantity: int) -> dict[str, Any]:
        return self.request(
            "PUT",
            f"products/{product_id}",
            payload={"manage_stock": True, "stock_quantity": int(stock_quantity)},
        )

    def update_product(self, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"products/{int(product_id)}", payload=payload)

    def update_variation(self, parent_product_id: int, variation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request(
            "PUT",
            f"products/{int(parent_product_id)}/variations/{int(variation_id)}",
            payload=payload,
        )
