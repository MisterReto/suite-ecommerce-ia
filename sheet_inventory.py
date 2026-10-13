"""Local physical inventory: existing Sheet rows, counts and identified movements."""
from __future__ import annotations
import asyncio
import time
from typing import Any
from fastapi import Request
from fastapi.responses import JSONResponse
import app as legacy_app
from app_security import public_error
from inventory_schema import MASTER_SHEET, normalize_product_row
from inventory_bulk import register_initial_counts
from inventory_operations import register_movement
_RECENT_SUBMITS: dict[str, float] = {}

def _read_master_inventory(session) -> tuple[str, list[dict[str, Any]]]:
    drive = legacy_app._get_drive_service(session)
    _, _, spreadsheet_id, _ = legacy_app._preparar_estructura(drive, session)
    sheets = legacy_app._get_sheets_service(session)
    legacy_app._validar_inventario_preparado(sheets, spreadsheet_id)
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MASTER_SHEET}'",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values = result.get("values", [])
    if len(values) < 2:
        return spreadsheet_id, []

    headers = [str(v).strip() for v in values[0]]
    rows = []
    for raw in values[1:]:
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        row = dict(zip(headers, padded[: len(headers)]))
        rows.append(normalize_product_row(row))
    return spreadsheet_id, rows


def _session(request: Request):
    sid = request.cookies.get("session_id")
    return legacy_app.SESSIONS.get(sid) if sid else None


def _context(request: Request):
    session = _session(request)
    if not session:
        raise PermissionError("Primero inicia sesión con Google Drive en la Suite.")
    drive = legacy_app._get_drive_service(session)
    _, _, spreadsheet_id, _ = legacy_app._preparar_estructura(drive, session)
    sheets = legacy_app._get_sheets_service(session)
    legacy_app._validar_inventario_preparado(sheets, spreadsheet_id)
    return session, spreadsheet_id, sheets


async def inventory_count_bulk(request: Request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("La solicitud debe ser un objeto JSON.")
        session, spreadsheet_id, sheets = await asyncio.to_thread(_context, request)
        result = await asyncio.to_thread(register_initial_counts,
            sheets,
            spreadsheet_id,
            payload.get("counts", []),
            user=session.get("email", ""),
        )
        return {"ok": True, "message": f"Se guardaron {result['updated']} conteos iniciales.", "result": result}
    except PermissionError as exc:
        return JSONResponse(status_code=401, content={"ok": False, "error": public_error(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": public_error(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": public_error(exc)})


async def inventory_movement(request: Request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("La solicitud debe ser un objeto JSON.")
        session, spreadsheet_id, sheets = await asyncio.to_thread(_context, request)
        fingerprint = "|".join([
            spreadsheet_id, str(session.get("email", "")), str(payload.get("sku", "")), str(payload.get("movement_type", "")),
            str(payload.get("quantity", "")), str(payload.get("reason", "")), str(payload.get("reference", "")),
        ])
        now = time.monotonic()
        last = _RECENT_SUBMITS.get(fingerprint)
        if last is not None and now - last < 8:
            return JSONResponse(status_code=409, content={"ok": False, "error": "Movimiento duplicado bloqueado. Espera unos segundos antes de repetirlo."})
        for key, stamp in list(_RECENT_SUBMITS.items()):
            if now - stamp >= 8:
                _RECENT_SUBMITS.pop(key, None)
        if len(_RECENT_SUBMITS) >= 4096:
            raise ValueError("Demasiados movimientos pendientes; espera unos segundos.")
        _RECENT_SUBMITS[fingerprint] = now
        result = await asyncio.to_thread(register_movement,
            sheets,
            spreadsheet_id,
            sku=payload.get("sku", ""),
            movement_type=payload.get("movement_type", ""),
            quantity=payload.get("quantity", 0),
            reason=payload.get("reason", ""),
            reference=payload.get("reference", ""),
            user=session.get("email", ""),
        )
        return {"ok": True,"message": f"{result['sku']}: stock {result['old_stock']} → {result['new_stock']} ({result['movement_type']}).","movement": result}
    except PermissionError as exc:
        return JSONResponse(status_code=401, content={"ok": False, "error": public_error(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": public_error(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": public_error(exc)})
