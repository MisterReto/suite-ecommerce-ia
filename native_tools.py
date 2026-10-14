"""Authenticated JSON tools for local Sheet counts and history."""
from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

import app as runtime
import sheet_inventory
from app_security import public_error
from inventory_operations import MOVEMENTS_SHEET, MOVEMENT_TYPES, inventory_summary, search_inventory
from inventory_schema import is_variable_parent


# Explicit method and role contracts; a read never starts a publication wave.
OPERATIONS = {"inventory": "GET", "history": "GET", "counts": "POST", "movement": "POST", "sync": "POST"}


def movements(sheets, sheet, sku="", limit=10000):
    """Read existing history without creating its sheet merely to show a screen."""
    book = sheets.spreadsheets().get(spreadsheetId=sheet,
        fields="sheets(properties(title))").execute()
    if not any(item["properties"]["title"] == MOVEMENTS_SHEET for item in book.get("sheets", [])):
        return []
    values = sheets.spreadsheets().values().get(spreadsheetId=sheet,
        range=f"'{MOVEMENTS_SHEET}'!A:K", valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
    if not values:
        return []
    headers = [str(item).strip() for item in values[0]]
    rows = [dict(zip(headers, list(row) + [""] * max(0, len(headers) - len(row)))) for row in values[1:]]
    return list(reversed([row for row in rows if not sku or str(row.get("sku", "")).strip() == sku][-limit:]))


def inventory(value, query):
    """Reuse the canonical inventory, with count flags and parent stock rules."""
    sheet, rows, sheets = inventory_context(value)
    counted = {str(row.get("sku", "")).strip() for row in movements(sheets, sheet)
               if row.get("tipo") == "Inventario inicial"}
    filtered = search_inventory(rows, query, limit=500)
    return {"ok": True, "total": len(rows), "summary": inventory_summary(rows),
            "pending": sum(not is_variable_parent(row) and row["sku"] not in counted for row in rows),
            "movement_types": list(MOVEMENT_TYPES),
            "rows": [{**row, "counted": row["sku"] in counted,
                      "variable_parent": is_variable_parent(row)} for row in filtered]}




async def execute(request, operation, value):
    if operation == "sync":
        from catalog_platform.sheet_sync import sync_inventory
        payload = await request.json()
        result = await asyncio.to_thread(sync_inventory, value, payload.get("skus"))
        return {"ok": True, "result": result, "message": f"Se sincronizaron {result['updated']} productos con el catálogo de la app."}
    if operation == "inventory":
        return await asyncio.to_thread(inventory, value, request.query_params.get("q", "")[:500])
    if operation == "history":
        sku = request.query_params.get("sku", "").strip()
        if not sku or len(sku) > 80:
            raise HTTPException(422, "Selecciona un SKU válido.")
        def read():
            sheet, _, sheets = inventory_context(value)
            return {"ok": True, "sku": sku, "rows": movements(sheets, sheet, sku, 50)}
        return await asyncio.to_thread(read)
    handler = {"counts": sheet_inventory.inventory_count_bulk, "movement": sheet_inventory.inventory_movement}[operation]
    return await handler(request)


def register(app):
    """Register local JSON operations on FastAPI."""
    @app.api_route("/api/tools/{operation}", methods=["GET", "POST"])
    async def tools(request: Request, operation: str):
        method = OPERATIONS.get(operation)
        if not method:
            raise HTTPException(404, "Herramienta no disponible.")
        if request.method != method:
            raise HTTPException(405, "Método no permitido.")
        sid = request.cookies.get("session_id")
        value = runtime.SESSIONS.get(sid) if sid else None
        if not value:
            raise HTTPException(401, "Conecta Google Drive para continuar.")
        from catalog_platform.security import require_role
        require_role(value, "admin", "editor", "viewer")
        if method == "POST":
            from catalog_platform.security import role_for
            role = value.get("role") or role_for(value.get("email", ""))
            allowed = {"admin", "editor"}
            if role not in allowed:
                raise HTTPException(403, "Tu rol no permite esta escritura.")
            try:
                payload = await request.json()
            except ValueError:
                raise HTTPException(422, "La solicitud debe ser JSON válido.") from None
            if not isinstance(payload, dict) or payload.get("confirm") is not True:
                raise HTTPException(422, "Confirma la operación antes de continuar.")
        try:
            return await execute(request, operation, value)
        except HTTPException:
            raise
        except ValueError as exc:
            return JSONResponse({"error": public_error(exc)}, status_code=422)
        except Exception as exc:
            return JSONResponse({"error": public_error(exc)}, status_code=502)



def inventory_context(value):
    sheet, rows = sheet_inventory._read_master_inventory(value)
    return sheet, rows, runtime._get_sheets_service(value)
