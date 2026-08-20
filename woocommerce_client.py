"""Cliente seguro para WooCommerce con keep-alive y payloads mínimos."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from dataclasses import dataclass
from threading import Lock
import time
from typing import Any, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class WooCommerceError(RuntimeError):
    pass


_CATALOG_CACHE: dict[
    tuple[str, bool],
    tuple[float, dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]],
] = {}
_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class WooCommerceConfig:
    base_url: str
    consumer_key: str = ""
    consumer_secret: str = ""
    write_enabled: bool = False
    timeout: int = 45
    max_workers: int = 3
    metadata_workers: int = 4
    cache_ttl: int = 120

    @classmethod
    def from_env(cls) -> "WooCommerceConfig":
        base_url = os.getenv("WC_URL", "https://rincon.creandotusite.com").rstrip("/")
        requested_workers = int(os.getenv("WC_MAX_WORKERS", "3"))
        requested_metadata = int(os.getenv("WC_METADATA_WORKERS", "4"))
        requested_ttl = int(os.getenv("WC_CACHE_TTL", "120"))
        return cls(
            base_url=base_url,
            consumer_key=os.getenv("WC_CONSUMER_KEY", "").strip(),
            consumer_secret=os.getenv("WC_CONSUMER_SECRET", "").strip(),
            write_enabled=os.getenv("WC_WRITE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
            timeout=max(10, int(os.getenv("WC_TIMEOUT", "45"))),
            max_workers=max(1, min(3, requested_workers)),
            metadata_workers=max(1, min(6, requested_metadata)),
            cache_ttl=max(0, min(1800, requested_ttl)),
        )

    @property
    def configured(self) -> bool:
        return bool(self.consumer_key and self.consumer_secret)


class WooCommerceClient:
    def __init__(self, config: WooCommerceConfig | None = None):
        self.config = config or WooCommerceConfig.from_env()
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=1,
            status=2,
            backoff_factor=0.35,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset({"GET", "PUT"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _auth_header(self) -> str:
        if not self.config.configured:
            raise WooCommerceError("Faltan WC_CONSUMER_KEY y WC_CONSUMER_SECRET en las variables de entorno.")
        raw = f"{self.config.consumer_key}:{self.config.consumer_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _invalidate_catalog_cache(self) -> None:
        with _CACHE_LOCK:
            for key in list(_CATALOG_CACHE):
                if key[0] == self.config.base_url:
                    _CATALOG_CACHE.pop(key, None)

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
        headers = {
            "Authorization": self._auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RinconDeAsia-SuiteEcommerceIA/1.0",
            "Connection": "keep-alive",
        }
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=payload,
                headers=headers,
                timeout=(10, self.config.timeout),
            )
            if response.status_code >= 400:
                raise WooCommerceError(
                    f"WooCommerce HTTP {response.status_code}: {response.text[:500]}"
                )
            parsed = response.json() if response.content else None
            if method != "GET":
                self._invalidate_catalog_cache()
            return parsed
        except requests.RequestException as exc:
            raise WooCommerceError(f"No se pudo conectar con WooCommerce: {exc}") from exc

    def list_products(self, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return self.request("GET", "products", params={"page": page, "per_page": per_page}) or []

    def list_products_catalog(self, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return self.request(
            "GET",
            "products",
            params={
                "page": page,
                "per_page": per_page,
                "_fields": "id,sku,name,type,manage_stock,stock_quantity,stock_status,regular_price,price,permalink",
            },
        ) or []

    def get_product(self, product_id: int) -> dict[str, Any]:
        return self.request("GET", f"products/{int(product_id)}") or {}

    def list_variations(self, product_id: int, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return self.request("GET", f"products/{int(product_id)}/variations", params={"page": page, "per_page": per_page}) or []

    def list_variations_catalog(self, product_id: int, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        return self.request(
            "GET",
            f"products/{int(product_id)}/variations",
            params={
                "page": page,
                "per_page": per_page,
                "_fields": "id,sku,manage_stock,stock_quantity,stock_status,regular_price,price",
            },
        ) or []

    def get_variation(self, parent_product_id: int, variation_id: int) -> dict[str, Any]:
        return self.request("GET", f"products/{int(parent_product_id)}/variations/{int(variation_id)}") or {}

    def list_setting_groups(self) -> list[dict[str, Any]]:
        return self.request("GET", "settings") or []

    def list_settings(self, group_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"settings/{group_id}") or []

    def get_setting(self, group_id: str, setting_id: str) -> dict[str, Any]:
        return self.request("GET", f"settings/{group_id}/{setting_id}") or {}

    def _iter_pages(self, getter, *, per_page: int = 100, max_pages: int = 100) -> Iterator[dict[str, Any]]:
        for page in range(1, max_pages + 1):
            batch = getter(page=page, per_page=per_page)
            for row in batch:
                yield row
            last = len(batch) < per_page
            if last:
                break

    def list_all_products(self) -> list[dict[str, Any]]:
        return list(self._iter_pages(self.list_products))

    def list_all_variations(self, product_id: int) -> list[dict[str, Any]]:
        return list(self._iter_pages(lambda **kw: self.list_variations(product_id, **kw)))

    def list_all_variations_catalog(self, product_id: int) -> list[dict[str, Any]]:
        return list(self._iter_pages(lambda **kw: self.list_variations_catalog(product_id, **kw)))

    @staticmethod
    def _slim(row: dict[str, Any], entity_type: str, parent_id: int | None = None) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "sku": row.get("sku", ""),
            "name": row.get("name", ""),
            "type": row.get("type"),
            "manage_stock": row.get("manage_stock"),
            "stock_quantity": row.get("stock_quantity"),
            "stock_status": row.get("stock_status"),
            "regular_price": row.get("regular_price"),
            "price": row.get("price"),
            "permalink": row.get("permalink"),
            "_entity_type": entity_type,
            "_parent_product_id": parent_id,
        }

    def catalog_by_sku(self, *, include_variations: bool = True, force_refresh: bool = False):
        cache_key = (self.config.base_url, include_variations)
        if not force_refresh and self.config.cache_ttl > 0:
            with _CACHE_LOCK:
                cached = _CATALOG_CACHE.get(cache_key)
                if cached and time.time() - cached[0] < self.config.cache_ttl:
                    return cached[1], cached[2]

        index: dict[str, dict[str, Any]] = {}
        duplicates: dict[str, list[dict[str, Any]]] = {}
        variable_ids: list[int] = []

        def add(row: dict[str, Any], entity_type: str, parent_id: int | None = None):
            sku = str(row.get("sku", "") or "").strip()
            if not sku:
                return
            item = self._slim(row, entity_type, parent_id)
            if sku in index:
                duplicates.setdefault(sku, [index[sku]]).append(item)
            else:
                index[sku] = item

        for product in self._iter_pages(self.list_products_catalog):
            add(product, "product")
            if include_variations and product.get("type") == "variable" and product.get("id"):
                variable_ids.append(int(product["id"]))

        if variable_ids:
            workers = min(self.config.metadata_workers, len(variable_ids))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="wc-meta") as executor:
                for start in range(0, len(variable_ids), workers * 2):
                    batch_ids = variable_ids[start:start + workers * 2]
                    futures = {
                        executor.submit(self.list_all_variations_catalog, parent_id): parent_id
                        for parent_id in batch_ids
                    }
                    for future in as_completed(futures):
                        parent_id = futures[future]
                        try:
                            variations = future.result()
                        except Exception as exc:
                            raise WooCommerceError(f"No pude leer variaciones del producto {parent_id}: {exc}") from exc
                        for variation in variations:
                            add(variation, "variation", parent_id=parent_id)
                    futures.clear()

        if self.config.cache_ttl > 0:
            with _CACHE_LOCK:
                _CATALOG_CACHE[cache_key] = (time.time(), index, duplicates)
        return index, duplicates

    def find_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        rows = self.request("GET", "products", params={"sku": sku, "per_page": 100})
        for row in rows or []:
            if str(row.get("sku", "")).strip() == str(sku).strip():
                return row
        return None

    def update_stock(self, product_id: int, stock_quantity: int) -> dict[str, Any]:
        return self.request("PUT", f"products/{product_id}", payload={"manage_stock": True, "stock_quantity": int(stock_quantity)})

    def update_product(self, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"products/{int(product_id)}", payload=payload)

    def update_variation(self, parent_product_id: int, variation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"products/{int(parent_product_id)}/variations/{int(variation_id)}", payload=payload)
