"""Comparación segura entre inventario canónico y WooCommerce.

Este módulo genera un preview; no modifica WooCommerce por sí solo.
Separa diferencias comerciales (nombre) de diferencias que afectan inventario.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from inventory_schema import normalize_product_row


@dataclass(frozen=True)
class SyncPreview:
    sku: str
    status: str
    product_id: int | None
    entity_type: str | None
    parent_product_id: int | None
    inventory_stock: int
    woocommerce_stock: int | None
    manages_stock: bool
    stock_status: str | None
    inventory_price: float
    woocommerce_price: float | None
    name_matches: bool
    changes: tuple[str, ...]
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _normalize_name(value: Any) -> str:
    """Normaliza solo para detectar cambios de texto sin castigar espacios/acentos."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _manages_stock(value: Any) -> bool:
    if value is True:
        return True
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def compare_product(inventory_row: Mapping[str, Any], wc_product: Mapping[str, Any] | None) -> SyncPreview:
    inv = normalize_product_row(inventory_row)
    sku = inv["sku"]
    inv_price = _money(inv["precio"])

    if not wc_product:
        return SyncPreview(
            sku=sku,
            status="missing_in_woocommerce",
            product_id=None,
            entity_type=None,
            parent_product_id=None,
            inventory_stock=inv["Existencias"],
            woocommerce_stock=None,
            manages_stock=False,
            stock_status=None,
            inventory_price=inv_price,
            woocommerce_price=None,
            name_matches=False,
            changes=("missing",),
            notes=("No existe un producto/variación con este SKU en WooCommerce.",),
        )

    wc_stock = wc_product.get("stock_quantity")
    try:
        wc_stock = int(wc_stock) if wc_stock is not None else None
    except (TypeError, ValueError):
        wc_stock = None

    manages_stock = _manages_stock(wc_product.get("manage_stock"))
    stock_status = str(wc_product.get("stock_status") or "").strip() or None
    wc_price = _money(wc_product.get("regular_price") or wc_product.get("price"))
    name_matches = _normalize_name(wc_product.get("name")) == _normalize_name(inv["nombre_producto"])

    changes: list[str] = []
    notes: list[str] = []

    # stock_quantity=None NO es una diferencia numérica si WooCommerce no está
    # administrando stock para ese producto/variación. Se reporta por separado.
    if manages_stock:
        if wc_stock != inv["Existencias"]:
            changes.append("stock")
    else:
        changes.append("stock_unmanaged")
        notes.append("WooCommerce no administra existencias para este SKU.")

    if wc_price != inv_price:
        changes.append("price")

    # El nombre es contenido comercial; nunca debe convertir por sí solo una fila
    # en una discrepancia de inventario.
    if not name_matches:
        changes.append("name")

    inventory_changes = {"stock", "price"}.intersection(changes)
    if inventory_changes:
        status = "inventory_mismatch"
    elif "stock_unmanaged" in changes:
        status = "stock_unmanaged"
    elif "name" in changes:
        status = "content_difference"
    else:
        status = "in_sync"

    return SyncPreview(
        sku=sku,
        status=status,
        product_id=wc_product.get("id"),
        entity_type=wc_product.get("_entity_type"),
        parent_product_id=wc_product.get("_parent_product_id"),
        inventory_stock=inv["Existencias"],
        woocommerce_stock=wc_stock,
        manages_stock=manages_stock,
        stock_status=stock_status,
        inventory_price=inv_price,
        woocommerce_price=wc_price,
        name_matches=name_matches,
        changes=tuple(changes),
        notes=tuple(notes),
    )
