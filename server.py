"""Integración segura de WooCommerce sobre la app FastAPI/Gradio existente.

No crea una segunda FastAPI: reutiliza la aplicación original para conservar el
lifespan y la cola de Gradio, y añade rutas WooCommerce en modo diagnóstico.
"""
from __future__ import annotations

import html
from collections import Counter
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount

import app as legacy_app
from inventory_schema import MASTER_SHEET, normalize_product_row, is_variable_parent
from woocommerce_client import WooCommerceClient, WooCommerceConfig, WooCommerceError
from woocommerce_inventory import compare_product
from store_connection import drive_only
from sync_bridge_protocol import TOOL_PATHS
from sync_gateway import redirect_tool, worker_enabled, install_handoff_routes

if worker_enabled():
    install_handoff_routes(legacy_app.fastapi_app, legacy_app)


def _current_session(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    return legacy_app.SESSIONS.get(session_id)


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


def _wc_config_status() -> dict[str, Any]:
    cfg = WooCommerceConfig.from_env()
    return {
        "configured": cfg.configured,
        "url": cfg.base_url,
        "write_enabled": cfg.write_enabled,
        "mode": "WRITE" if cfg.write_enabled else "READ ONLY",
    }


def _connection_test() -> dict[str, Any]:
    client = WooCommerceClient()
    cfg = client.config
    if not cfg.configured:
        raise WooCommerceError("Faltan WC_CONSUMER_KEY y/o WC_CONSUMER_SECRET en Render.")
    products = client.list_products(page=1, per_page=1)
    return {
        "ok": True,
        "url": cfg.base_url,
        "write_enabled": cfg.write_enabled,
        "sample_products_received": len(products),
        "sample": ({
            "id": products[0].get("id"),
            "name": products[0].get("name"),
            "sku": products[0].get("sku"),
            "type": products[0].get("type"),
        } if products else None),
    }


def _stock_source_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [int(row.get("Existencias", 0) or 0) for row in rows if not is_variable_parent(row)]
    counts = Counter(values)
    unique_values = sorted(counts)
    all_same = bool(values) and len(unique_values) == 1
    suspicious_placeholder = bool(values) and all_same and unique_values[0] in {0, 1}
    return {
        "row_count": len(values),
        "unique_values": unique_values,
        "distribution": dict(sorted(counts.items())),
        "all_same": all_same,
        "suspicious_placeholder": suspicious_placeholder,
        "safe_for_automatic_stock_write": not suspicious_placeholder,
        "warning": (
            f"Las {len(values)} filas tienen Existencias={unique_values[0]}. "
            "Ese patrón parece un valor de carga inicial, no un conteo físico; la escritura automática de stock queda bloqueada."
            if suspicious_placeholder else ""
        ),
    }


def _build_preview(rows, *, limit: int | None = None):
    client = WooCommerceClient()
    wc_index, duplicate_skus = client.catalog_by_sku(include_variations=True)
    selected = rows if not limit or limit <= 0 else rows[:limit]

    previews = []
    counts = {
        "total_inventory": len(rows),
        "checked": len(selected),
        "in_sync": 0,
        "inventory_mismatch": 0,
        "stock_unmanaged": 0,
        "content_difference": 0,
        "missing_in_woocommerce": 0,
        "duplicate_wc_skus": len(duplicate_skus),
    }
    for row in selected:
        preview = compare_product(row, wc_index.get(row["sku"]))
        data = preview.as_dict()
        data["name"] = row.get("nombre_producto", "")
        data["brand"] = row.get("Marca", "")
        data["category"] = row.get("categorias", "")
        data["changes"] = list(data["changes"])
        data["notes"] = list(data["notes"])
        previews.append(data)
        counts[data["status"]] = counts.get(data["status"], 0) + 1

    return {
        "summary": counts,
        "source_stock": _stock_source_profile(rows),
        "woocommerce": _wc_config_status(),
        "duplicate_skus": sorted(duplicate_skus.keys()),
        "rows": previews,
    }


fastapi_app = legacy_app.fastapi_app


@fastapi_app.middleware("http")
async def pause_store_tools(request: Request, call_next):
    path = request.url.path.rstrip("/")
    store_tool = path in TOOL_PATHS or path.startswith((
        "/woocommerce-", "/wc-", "/wp-media-", "/product-sync-",
        "/image-sync-", "/stock-preview-", "/batch-",
    ))
    if drive_only() and store_tool:
        message = "Conexión con la tienda pausada. La app guarda únicamente en Google Drive."
        if request.method == "GET" and (path == "/inventory-sync" or path.startswith("/woocommerce-")):
            return HTMLResponse(
                "<!doctype html><html lang='es'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Solo Drive</title><body style='font:18px system-ui;padding:24px;background:white;color:#172033'>"
                f"<h1>Modo solo Drive</h1><p>{message}</p><a href='/'>Volver a la app</a></body></html>"
            )
        return JSONResponse({"error": message, "mode": "drive_only"}, status_code=503)
    if worker_enabled() and store_tool:
        if path not in TOOL_PATHS:
            return JSONResponse({"error": "Herramienta no disponible."}, status_code=404)
        return redirect_tool(request)
    return await call_next(request)


@fastapi_app.get("/wc-health")
def wc_health():
    try:
        return _connection_test()
    except Exception as exc:
        return JSONResponse(status_code=502, content={"ok": False, "error": str(exc), **_wc_config_status()})


@fastapi_app.get("/wc-preview")
def wc_preview(request: Request, limit: int = 50):
    session = _current_session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Primero inicia sesión con Google Drive en la app."})
    try:
        _, rows = _read_master_inventory(session)
        payload = _build_preview(rows, limit=limit)
        payload["ok"] = True
        return payload
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@fastapi_app.get("/inventory-sync")
def inventory_sync_dashboard(request: Request):
    return RedirectResponse("/inventory-hub#review", status_code=303)


_root_gradio_mounts = [route for route in fastapi_app.router.routes if isinstance(route, Mount) and getattr(route, "path", None) in {"", "/"}]
if _root_gradio_mounts:
    fastapi_app.router.routes[:] = [route for route in fastapi_app.router.routes if route not in _root_gradio_mounts] + _root_gradio_mounts

