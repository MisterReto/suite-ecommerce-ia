"""JSON adapters for tools inside Next.js; the established business functions stay intact.

The main API may forward a signed request to the sync backend. That backend exposes
only /internal/tools publicly after retirement; it never serves the old interface.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

import app as runtime
import batch_web_v2
import inventory_web
import media_web
import product_web
import publication_web
from app_security import public_error
from inventory_operations import MOVEMENTS_SHEET, MOVEMENT_TYPES, inventory_summary, search_inventory
from inventory_schema import is_variable_parent
from sync_gateway import forward_tool, worker_enabled


# Explicit method and role contracts; a read never starts a publication wave.
OPERATIONS = {
    "inventory": "GET", "history": "GET", "review": "GET", "media-preview": "GET",
    "batch-status": "GET", "counts": "POST", "movement": "POST",
    "media-sync": "POST", "product-sync": "POST", "batch-create": "POST",
    "batch-step": "POST", "batch-resume": "POST",
}
STORE_OPERATIONS = {"review", "media-preview", "media-sync", "product-sync",
                    "batch-create", "batch-status", "batch-step", "batch-resume"}


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
    sheet, rows, sheets = media_web._direct_inventory_context(value)
    counted = {str(row.get("sku", "")).strip() for row in movements(sheets, sheet)
               if row.get("tipo") == "Inventario inicial"}
    filtered = search_inventory(rows, query, limit=500)
    return {"ok": True, "total": len(rows), "summary": inventory_summary(rows),
            "pending": sum(not is_variable_parent(row) and row["sku"] not in counted for row in rows),
            "movement_types": list(MOVEMENT_TYPES),
            "rows": [{**row, "counted": row["sku"] in counted,
                      "variable_parent": is_variable_parent(row)} for row in filtered]}


def media_preview(value):
    """Return the same Drive/WordPress comparison as JSON, without an HTML page."""
    sheet, rows, sheets = media_web._direct_inventory_context(value)
    drive_index = media_web._drive_index(value)
    cache = media_web.read_media_cache(sheets, sheet)
    wc = media_web.WooCommerceClient()
    index, duplicates = wc.catalog_by_sku(include_variations=True)
    result = media_web.build_image_preview(rows, drive_index, index, duplicates, cache)
    wp = media_web.WordPressMediaClient()
    return {"ok": True, **result, "woocommerce_write": bool(wc.config.write_enabled),
            "wordpress_write": bool(wp.write_enabled), "wordpress_configured": bool(wp.configured)}


async def execute(request, operation, value):
    """Delegate to established handlers; no automatic retry of an external write."""
    if operation == "inventory":
        return await asyncio.to_thread(inventory, value, request.query_params.get("q", "")[:500])
    if operation == "history":
        sku = request.query_params.get("sku", "").strip()
        if not sku or len(sku) > 80:
            raise HTTPException(422, "Selecciona un SKU válido.")
        def read():
            sheet, _, sheets = media_web._direct_inventory_context(value)
            return {"ok": True, "sku": sku, "rows": movements(sheets, sheet, sku, 50)}
        return await asyncio.to_thread(read)
    if operation == "media-preview":
        return await asyncio.to_thread(media_preview, value)
    if operation == "review":
        return await asyncio.to_thread(publication_web.inventory_review, request)
    if operation == "batch-status":
        batch_id = request.query_params.get("batch_id", "").strip()
        if not batch_id or len(batch_id) > 100:
            raise HTTPException(422, "Selecciona un lote válido.")
        return await asyncio.to_thread(batch_web_v2.batch_status, request, batch_id)
    handler = {
        "counts": inventory_web.inventory_count_bulk, "movement": inventory_web.inventory_movement,
        "media-sync": media_web.image_sync_one, "product-sync": product_web.product_sync_one,
        "batch-create": batch_web_v2.batch_create, "batch-step": batch_web_v2.batch_step,
        "batch-resume": batch_web_v2.batch_resume,
    }[operation]
    return await handler(request)


def register(app):
    """Register the identical JSON contract on the public API and signed sync executor."""
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
        if os.getenv("SUITE_SERVICE_ROLE", "main").lower() != "sync":
            from catalog_platform.security import require_role
            require_role(value, "admin", "editor", "viewer")
        if operation in STORE_OPERATIONS and os.getenv("SUITE_DRIVE_ONLY", "true").lower() != "false":
            raise HTTPException(503, "La conexión con la tienda está pausada.")
        if method == "POST":
            from catalog_platform.security import role_for
            role = value.get("role") or role_for(value.get("email", ""))
            allowed = {"admin"} if operation in STORE_OPERATIONS else {"admin", "editor"}
            if role not in allowed:
                raise HTTPException(403, "Tu rol no permite esta escritura.")
            try:
                payload = await request.json()
            except ValueError:
                raise HTTPException(422, "La solicitud debe ser JSON válido.") from None
            if not isinstance(payload, dict) or payload.get("confirm") is not True:
                raise HTTPException(422, "Confirma la operación antes de continuar.")
        if worker_enabled():
            return await forward_tool(request, runtime)
        try:
            return await execute(request, operation, value)
        except HTTPException:
            raise
        except ValueError as exc:
            return JSONResponse({"error": public_error(exc)}, status_code=422)
        except Exception as exc:
            return JSONResponse({"error": public_error(exc)}, status_code=502)

