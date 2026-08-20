"""Lotes persistentes de sincronización WooCommerce.

El estado vive en Google Sheets. Las operaciones frecuentes usan actualizaciones
E:I directas para evitar un GET previo por cada cambio de estado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
import uuid
from typing import Any

BATCH_SHEET = "WooCommerce Batch Sync"
BATCH_COLUMNS = (
    "batch_id", "created_at", "position", "sku", "status", "message",
    "started_at", "finished_at", "permalink",
)

_READY_LOCK = Lock()
_READY_GIDS: dict[str, int] = {}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sheet_map(sheets_service, spreadsheet_id: str) -> dict[str, int]:
    book = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    return {
        item["properties"]["title"]: int(item["properties"]["sheetId"])
        for item in book.get("sheets", [])
    }


def ensure_batch_sheet(sheets_service, spreadsheet_id: str) -> int:
    with _READY_LOCK:
        cached = _READY_GIDS.get(spreadsheet_id)
    if cached is not None:
        return cached

    sheets = _sheet_map(sheets_service, spreadsheet_id)
    gid = sheets.get(BATCH_SHEET)
    if gid is None:
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": BATCH_SHEET}}}]},
        ).execute()
        gid = int(response["replies"][0]["addSheet"]["properties"]["sheetId"])

    current = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{BATCH_SHEET}'!A1:I1",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [])
    if not current or list(current[0]) != list(BATCH_COLUMNS):
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{BATCH_SHEET}'!A1:I1",
            valueInputOption="RAW",
            body={"values": [list(BATCH_COLUMNS)]},
        ).execute()

    with _READY_LOCK:
        _READY_GIDS[spreadsheet_id] = int(gid)
    return int(gid)


def _all_rows(sheets_service, spreadsheet_id: str) -> list[dict[str, Any]]:
    ensure_batch_sheet(sheets_service, spreadsheet_id)
    values = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{BATCH_SHEET}'!A:I",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [])
    if len(values) < 2:
        return []
    headers = [str(v) for v in values[0]]
    result = []
    for sheet_row, raw in enumerate(values[1:], start=2):
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        row = dict(zip(headers, padded[:len(headers)]))
        row["_sheet_row"] = sheet_row
        try:
            row["position"] = int(float(row.get("position") or 0))
        except (TypeError, ValueError):
            row["position"] = 0
        result.append(row)
    return result


def successful_skus(sheets_service, spreadsheet_id: str) -> set[str]:
    return {
        str(row.get("sku") or "").strip()
        for row in _all_rows(sheets_service, spreadsheet_id)
        if str(row.get("status") or "") == "success" and str(row.get("sku") or "").strip()
    }


def processed_skus(sheets_service, spreadsheet_id: str) -> set[str]:
    return {
        str(row.get("sku") or "").strip()
        for row in _all_rows(sheets_service, spreadsheet_id)
        if str(row.get("sku") or "").strip()
    }


def create_batch(sheets_service, spreadsheet_id: str, skus: list[str]) -> str:
    ensure_batch_sheet(sheets_service, spreadsheet_id)
    clean = []
    seen = set()
    for sku in skus:
        sku = str(sku or "").strip()
        if sku and sku not in seen:
            seen.add(sku)
            clean.append(sku)
    if not clean:
        raise ValueError("El lote no contiene SKU.")

    batch_id = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:5].upper()}"
    created = _now()
    rows = [
        [batch_id, created, pos, sku, "pending", "", "", "", ""]
        for pos, sku in enumerate(clean, start=1)
    ]
    sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{BATCH_SHEET}'!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return batch_id


def read_batch(sheets_service, spreadsheet_id: str, batch_id: str) -> list[dict[str, Any]]:
    result = []
    for row in _all_rows(sheets_service, spreadsheet_id):
        if str(row.get("batch_id") or "") == batch_id:
            result.append(row)
    return sorted(result, key=lambda r: r["position"])


def update_batch_item_fast(
    sheets_service,
    spreadsheet_id: str,
    *,
    sheet_row: int,
    status: str,
    message: str = "",
    started_at: str = "",
    finished_at: str = "",
    permalink: str = "",
) -> None:
    """Actualiza solo E:I en una llamada; ideal para el loop de sincronización."""
    ensure_batch_sheet(sheets_service, spreadsheet_id)
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{BATCH_SHEET}'!E{sheet_row}:I{sheet_row}",
        valueInputOption="RAW",
        body={"values": [[
            str(status or ""),
            str(message or "")[:1000],
            str(started_at or ""),
            str(finished_at or ""),
            str(permalink or ""),
        ]]},
    ).execute()


def update_batch_item(
    sheets_service,
    spreadsheet_id: str,
    *,
    sheet_row: int,
    status: str,
    message: str = "",
    started_at: str | None = None,
    finished_at: str | None = None,
    permalink: str = "",
) -> None:
    """Compatibilidad: preserva campos omitidos leyendo la fila antes de escribir."""
    current = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{BATCH_SHEET}'!A{sheet_row}:I{sheet_row}",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [[]])
    row = list(current[0] if current else []) + [""] * 9
    row = row[:9]
    row[4] = status
    row[5] = str(message or "")[:1000]
    if started_at is not None:
        row[6] = started_at
    if finished_at is not None:
        row[7] = finished_at
    if permalink:
        row[8] = permalink
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{BATCH_SHEET}'!A{sheet_row}:I{sheet_row}",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()


def batch_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"total": len(rows), "pending": 0, "running": 0, "success": 0, "error": 0}
    for row in rows:
        status = str(row.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
    counts["done"] = counts.get("success", 0) + counts.get("error", 0)
    counts["percent"] = round((counts.get("success", 0) / len(rows) * 100), 1) if rows else 0
    return counts
