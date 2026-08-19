"""Conteo inicial masivo con trazabilidad.

Permite registrar existencias físicas para muchos SKU en una sola operación de
Google Sheets. No modifica WooCommerce.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from inventory_operations import (
    MOVEMENTS_SHEET,
    _cell_value,
    _clean_text,
    _sheet_map,
    ensure_movements_sheet,
    read_inventory,
    read_movements,
)
from inventory_schema import MASTER_SHEET


def counted_initial_skus(sheets_service, spreadsheet_id: str) -> set[str]:
    rows = read_movements(sheets_service, spreadsheet_id, sku="", limit=10000)
    return {
        _clean_text(row.get("sku"))
        for row in rows
        if _clean_text(row.get("tipo")) == "Inventario inicial" and _clean_text(row.get("sku"))
    }


def register_initial_counts(
    sheets_service,
    spreadsheet_id: str,
    counts: list[dict[str, Any]],
    *,
    user: str = "",
    reference: str = "Conteo inicial masivo",
    reason: str = "Conteo físico inicial",
) -> dict[str, Any]:
    if not counts:
        raise ValueError("No recibí ningún conteo para guardar.")
    if len(counts) > 500:
        raise ValueError("Máximo 500 SKU por operación.")

    inventory = read_inventory(sheets_service, spreadsheet_id)
    by_sku: dict[str, list[dict[str, Any]]] = {}
    for row in inventory:
        by_sku.setdefault(_clean_text(row.get("sku")), []).append(row)

    normalized: list[tuple[dict[str, Any], int]] = []
    seen = set()
    errors = []
    for item in counts:
        sku = _clean_text(item.get("sku"))
        if not sku or sku in seen:
            continue
        seen.add(sku)
        matches = by_sku.get(sku, [])
        if not matches:
            errors.append(f"SKU no encontrado: {sku}")
            continue
        if len(matches) > 1:
            errors.append(f"SKU duplicado en {MASTER_SHEET}: {sku}")
            continue
        try:
            stock = int(float(item.get("stock")))
        except (TypeError, ValueError):
            errors.append(f"Conteo inválido para {sku}")
            continue
        if stock < 0:
            errors.append(f"El stock de {sku} no puede ser negativo")
            continue
        normalized.append((matches[0], stock))

    if errors:
        raise ValueError("; ".join(errors[:12]))
    if not normalized:
        raise ValueError("No hay conteos válidos para guardar.")

    sheets = _sheet_map(sheets_service, spreadsheet_id)
    master_gid = sheets.get(MASTER_SHEET)
    if master_gid is None:
        raise RuntimeError(f"No existe la pestaña '{MASTER_SHEET}'.")
    movements_gid = ensure_movements_sheet(sheets_service, spreadsheet_id)

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    requests = []
    results = []
    for product, new_stock in normalized:
        old_stock = int(product.get("Existencias", 0) or 0)
        delta = new_stock - old_stock
        movement_id = (
            f"MOV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-"
            f"{uuid.uuid4().hex[:6].upper()}"
        )
        movement_row = [
            now,
            movement_id,
            _clean_text(product.get("sku")),
            _clean_text(product.get("nombre_producto")),
            "Inventario inicial",
            delta,
            old_stock,
            new_stock,
            _clean_text(reason),
            _clean_text(reference),
            _clean_text(user),
        ]
        requests.extend([
            {
                "updateCells": {
                    "start": {
                        "sheetId": master_gid,
                        "rowIndex": int(product["_sheet_row"]) - 1,
                        "columnIndex": 7,
                    },
                    "rows": [{"values": [_cell_value(new_stock)]}],
                    "fields": "userEnteredValue",
                }
            },
            {
                "appendCells": {
                    "sheetId": movements_gid,
                    "rows": [{"values": [_cell_value(v) for v in movement_row]}],
                    "fields": "userEnteredValue",
                }
            },
        ])
        results.append({
            "sku": product["sku"],
            "old_stock": old_stock,
            "new_stock": new_stock,
            "delta": delta,
            "movement_id": movement_id,
        })

    # Stock + bitácora de todos los SKU se confirman en una sola batchUpdate.
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()

    return {
        "updated": len(results),
        "results": results,
    }
