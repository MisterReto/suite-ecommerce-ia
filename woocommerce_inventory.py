"""Comparación segura entre inventario canónico y WooCommerce.

Este módulo genera un preview; no modifica WooCommerce por sí solo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from inventory_schema import normalize_product_row


@dataclass(frozen=True)
class SyncPreview:
    sku: str
    status: str
    product_id: int | None
    inventory_stock: int
    woocommerce_stock: int | None
    inventory_price: float
    woocommerce_price: float | None
    changes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def compare_product(inventory_row: Mapping[str, Any], wc_product: Mapping[str, Any] | None) -> SyncPreview:
    inv = normalize_product_row(inventory_row)
    sku = inv["sku"]
    if not wc_product:
        return SyncPreview(
            sku=sku,
            status="missing_in_woocommerce",
            product_id=None,
            inventory_stock=inv["Existencias"],
            woocommerce_stock=None,
            inventory_price=_money(inv["precio"]),
            woocommerce_price=None,
            changes=("create_or_link_product",),
        )

    wc_stock = wc_product.get("stock_quantity")
    try:
        wc_stock = int(wc_stock) if wc_stock is not None else None
    except (TypeError, ValueError):
        wc_stock = None
    wc_price = _money(wc_product.get("regular_price") or wc_product.get("price"))
    inv_price = _money(inv["precio"])
    changes: list[str] = []
    if wc_stock != inv["Existencias"]:
        changes.append("stock")
    if wc_price != inv_price:
        changes.append("price")
    if str(wc_product.get("name", "")).strip() != str(inv["nombre_producto"]).strip():
        changes.append("name")

    return SyncPreview(
        sku=sku,
        status="update_needed" if changes else "in_sync",
        product_id=wc_product.get("id"),
        inventory_stock=inv["Existencias"],
        woocommerce_stock=wc_stock,
        inventory_price=inv_price,
        woocommerce_price=wc_price,
        changes=tuple(changes),
    )
