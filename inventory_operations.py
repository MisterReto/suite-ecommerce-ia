"""Operaciones de inventario físico para El Rincón de Asia.

La fuente de verdad es la pestaña `Lista completa` del Sheet `inventario_completo`.
Cada modificación de existencias se registra en `Movimientos Inventario`.
Este módulo NO escribe en WooCommerce.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata
import uuid
from typing import Any

from inventory_schema import MASTER_COLUMNS, MASTER_SHEET, normalize_product_row

MOVEMENTS_SHEET = "Movimientos Inventario"
MOVEMENT_COLUMNS = (
    "timestamp",
    "movement_id",
    "sku",
    "producto",
    "tipo",
    "cantidad",
    "stock_anterior",
    "stock_nuevo",
    "motivo",
    "referencia",
    "usuario",
)

MOVEMENT_TYPES = (
    "Inventario inicial",
    "Entrada",
    "Salida",
    "Merma",
    "Devolución",
    "Ajuste",
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _search_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean_text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _cell_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"userEnteredValue": {"boolValue": value}}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"userEnteredValue": {"numberValue": float(value)}}
    return {"userEnteredValue": {"stringValue": _clean_text(value)}}


def _sheet_map(sheets_service, spreadsheet_id: str) -> dict[str, int]:
    book = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    return {
        item["properties"]["title"]: item["properties"]["sheetId"]
        for item in book.get("sheets", [])
    }


def ensure_movements_sheet(sheets_service, spreadsheet_id: str) -> int:
    sheets = _sheet_map(sheets_service, spreadsheet_id)
    gid = sheets.get(MOVEMENTS_SHEET)
    if gid is None:
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {"addSheet": {"properties": {"title": MOVEMENTS_SHEET}}}
                ]
            },
        ).execute()
        gid = response["replies"][0]["addSheet"]["properties"]["sheetId"]

    # Asegura encabezados y formato básico sin alterar los movimientos existentes.
    current = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MOVEMENTS_SHEET}'!A1:K1",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [])
    if not current or list(current[0]) != list(MOVEMENT_COLUMNS):
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{MOVEMENTS_SHEET}'!A1:K1",
            valueInputOption="RAW",
            body={"values": [list(MOVEMENT_COLUMNS)]},
        ).execute()

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": gid,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": gid,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(MOVEMENT_COLUMNS),
                        },
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
            ]
        },
    ).execute()
    return gid


def read_inventory(sheets_service, spreadsheet_id: str) -> list[dict[str, Any]]:
    response = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MASTER_SHEET}'!A:N",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values = response.get("values", [])
    if len(values) < 2:
        return []

    headers = [_clean_text(v) for v in values[0]]
    rows: list[dict[str, Any]] = []
    for sheet_row_number, raw in enumerate(values[1:], start=2):
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        data = normalize_product_row(dict(zip(headers, padded[: len(headers)])))
        data["_sheet_row"] = sheet_row_number
        rows.append(data)
    return rows


def search_inventory(rows: list[dict[str, Any]], query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    query_key = _search_key(query)
    if not query_key:
        return rows[:limit]

    result = []
    for row in rows:
        haystack = " | ".join(
            _search_key(row.get(key))
            for key in ("sku", "nombre_producto", "Marca", "categorias")
        )
        if query_key in haystack:
            result.append(row)
            if len(result) >= limit:
                break
    return result


def inventory_table(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            row.get("sku", ""),
            row.get("nombre_producto", ""),
            row.get("Marca", ""),
            row.get("categorias", ""),
            row.get("Existencias", 0),
            row.get("precio", 0),
        ]
        for row in rows
    ]


def inventory_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    units = sum(max(0, int(row.get("Existencias", 0) or 0)) for row in rows)
    retail_value = sum(
        max(0, int(row.get("Existencias", 0) or 0)) * float(row.get("precio", 0) or 0)
        for row in rows
    )
    out_of_stock = sum(1 for row in rows if int(row.get("Existencias", 0) or 0) <= 0)
    low_stock = sum(1 for row in rows if 0 < int(row.get("Existencias", 0) or 0) <= 3)
    return {
        "products": len(rows),
        "units": units,
        "retail_value": round(retail_value, 2),
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
    }


def _find_unique_sku(rows: list[dict[str, Any]], sku: str) -> dict[str, Any]:
    sku = _clean_text(sku)
    matches = [row for row in rows if _clean_text(row.get("sku")) == sku]
    if not matches:
        raise ValueError(f"No encontré el SKU '{sku}' en {MASTER_SHEET}.")
    if len(matches) > 1:
        raise ValueError(f"El SKU '{sku}' está duplicado en {MASTER_SHEET}; corrígelo antes de mover stock.")
    return matches[0]


def read_movements(sheets_service, spreadsheet_id: str, sku: str = "", limit: int = 50) -> list[dict[str, Any]]:
    ensure_movements_sheet(sheets_service, spreadsheet_id)
    response = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MOVEMENTS_SHEET}'!A:K",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values = response.get("values", [])
    if len(values) < 2:
        return []
    headers = [_clean_text(v) for v in values[0]]
    target = _clean_text(sku)
    rows = []
    for raw in values[1:]:
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        row = dict(zip(headers, padded[: len(headers)]))
        if target and _clean_text(row.get("sku")) != target:
            continue
        rows.append(row)
    return list(reversed(rows[-limit:]))


def movements_table(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            row.get("timestamp", ""),
            row.get("movement_id", ""),
            row.get("tipo", ""),
            row.get("cantidad", ""),
            row.get("stock_anterior", ""),
            row.get("stock_nuevo", ""),
            row.get("motivo", ""),
            row.get("referencia", ""),
            row.get("usuario", ""),
        ]
        for row in rows
    ]


def register_movement(
    sheets_service,
    spreadsheet_id: str,
    *,
    sku: str,
    movement_type: str,
    quantity: Any,
    reason: str = "",
    reference: str = "",
    user: str = "",
) -> dict[str, Any]:
    if movement_type not in MOVEMENT_TYPES:
        raise ValueError("Tipo de movimiento inválido.")
    try:
        qty = int(float(quantity))
    except (TypeError, ValueError):
        raise ValueError("La cantidad debe ser un número entero.")

    if movement_type in {"Inventario inicial", "Ajuste"}:
        if qty < 0:
            raise ValueError("El stock final no puede ser negativo.")
    elif qty <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    rows = read_inventory(sheets_service, spreadsheet_id)
    product = _find_unique_sku(rows, sku)
    old_stock = int(product.get("Existencias", 0) or 0)

    if movement_type in {"Inventario inicial", "Ajuste"}:
        new_stock = qty
        signed_quantity = new_stock - old_stock
    elif movement_type in {"Entrada", "Devolución"}:
        new_stock = old_stock + qty
        signed_quantity = qty
    else:  # Salida / Merma
        new_stock = old_stock - qty
        signed_quantity = -qty

    if new_stock < 0:
        raise ValueError(
            f"Movimiento rechazado: stock actual {old_stock}; no puedes dejar el SKU en {new_stock}."
        )

    sheets = _sheet_map(sheets_service, spreadsheet_id)
    master_gid = sheets.get(MASTER_SHEET)
    if master_gid is None:
        raise RuntimeError(f"No existe la pestaña '{MASTER_SHEET}'.")
    movements_gid = ensure_movements_sheet(sheets_service, spreadsheet_id)

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    movement_id = f"MOV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    movement_row = [
        now,
        movement_id,
        _clean_text(product.get("sku")),
        _clean_text(product.get("nombre_producto")),
        movement_type,
        signed_quantity,
        old_stock,
        new_stock,
        _clean_text(reason),
        _clean_text(reference),
        _clean_text(user),
    ]

    # updateCells + appendCells via una sola batchUpdate: stock y bitácora se
    # confirman juntos o falla toda la operación.
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateCells": {
                        "start": {
                            "sheetId": master_gid,
                            "rowIndex": int(product["_sheet_row"]) - 1,
                            "columnIndex": 7,  # H = Existencias
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
            ]
        },
    ).execute()

    return {
        "movement_id": movement_id,
        "sku": product["sku"],
        "product": product["nombre_producto"],
        "movement_type": movement_type,
        "quantity": signed_quantity,
        "old_stock": old_stock,
        "new_stock": new_stock,
    }
