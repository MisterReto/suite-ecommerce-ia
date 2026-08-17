"""Integración segura de WooCommerce sobre la app FastAPI/Gradio existente.

No crea una segunda FastAPI: reutiliza la aplicación original para conservar el
lifespan y la cola de Gradio, y añade rutas WooCommerce en modo diagnóstico.
"""
from __future__ import annotations

import html
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount

import app as legacy_app
from inventory_schema import MASTER_SHEET, normalize_product_row
from woocommerce_client import WooCommerceClient, WooCommerceConfig, WooCommerceError
from woocommerce_inventory import compare_product


def _current_session(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    return legacy_app.SESSIONS.get(session_id)


def _read_master_inventory(session) -> tuple[str, list[dict[str, Any]]]:
    drive = legacy_app._get_drive_service(session)
    manual_folder = session.get("carpeta_raiz_id_manual")
    if manual_folder:
        root_folder_id = manual_folder
    else:
        root_folder_id = legacy_app._buscar_o_crear_carpeta(
            drive, legacy_app.NOMBRE_CARPETA_RAIZ
        )

    spreadsheet_id = legacy_app._buscar_archivo(
        drive,
        legacy_app.NOMBRE_GOOGLE_SHEET,
        root_folder_id,
        mime_type="application/vnd.google-apps.spreadsheet",
    )
    if not spreadsheet_id:
        raise RuntimeError(
            "No encontré 'inventario_completo' en la carpeta configurada de Google Drive."
        )

    sheets = legacy_app._get_sheets_service(session)
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MASTER_SHEET}'!A:N",
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
        raise WooCommerceError(
            "Faltan WC_CONSUMER_KEY y/o WC_CONSUMER_SECRET en Render."
        )
    products = client.list_products(page=1, per_page=1)
    return {
        "ok": True,
        "url": cfg.base_url,
        "write_enabled": cfg.write_enabled,
        "sample_products_received": len(products),
        "sample": (
            {
                "id": products[0].get("id"),
                "name": products[0].get("name"),
                "sku": products[0].get("sku"),
                "type": products[0].get("type"),
            }
            if products
            else None
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
        "update_needed": 0,
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
        previews.append(data)
        counts[data["status"]] = counts.get(data["status"], 0) + 1

    return {
        "summary": counts,
        "woocommerce": _wc_config_status(),
        "duplicate_skus": sorted(duplicate_skus.keys()),
        "rows": previews,
    }


# Misma app que ya contiene OAuth + Gradio.
fastapi_app = legacy_app.fastapi_app


@fastapi_app.get("/wc-health")
def wc_health():
    try:
        return _connection_test()
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"ok": False, "error": str(exc), **_wc_config_status()},
        )


@fastapi_app.get("/wc-preview")
def wc_preview(request: Request, limit: int = 50):
    session = _current_session(request)
    if not session:
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "Primero inicia sesión con Google Drive en la app."},
        )
    try:
        _, rows = _read_master_inventory(session)
        payload = _build_preview(rows, limit=limit)
        payload["ok"] = True
        return payload
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@fastapi_app.get("/inventory-sync", response_class=HTMLResponse)
def inventory_sync_dashboard(request: Request):
    cfg = _wc_config_status()
    session = _current_session(request)
    login_state = "✅ Google Drive conectado" if session else "⚠️ Inicia sesión con Google Drive primero"
    write_state = "🔴 Escrituras habilitadas" if cfg["write_enabled"] else "🟢 Modo seguro: SOLO LECTURA"
    body = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Inventario ↔ WooCommerce</title>
      <style>
        body {{ font-family: Arial, sans-serif; max-width: 980px; margin: 40px auto; padding: 0 20px; background:#fafafa; color:#1f2937; }}
        .card {{ background:white; padding:22px; border-radius:14px; margin:16px 0; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
        a.btn {{ display:inline-block; padding:10px 14px; margin:6px 8px 6px 0; border-radius:9px; background:#111827; color:white; text-decoration:none; }}
        code {{ background:#f3f4f6; padding:2px 5px; border-radius:4px; }}
      </style>
    </head>
    <body>
      <h1>📦 Inventario ↔ WooCommerce</h1>
      <div class="card">
        <p><b>{html.escape(login_state)}</b></p>
        <p><b>{html.escape(write_state)}</b></p>
        <p>Tienda: <code>{html.escape(cfg["url"])}</code></p>
        <p>Este panel no modifica productos, precios ni existencias.</p>
      </div>
      <div class="card">
        <h2>Diagnóstico</h2>
        <a class="btn" href="/wc-health" target="_blank">1. Probar conexión WooCommerce</a>
        <a class="btn" href="/wc-preview?limit=20" target="_blank">2. Comparar 20 SKU</a>
        <a class="btn" href="/wc-preview?limit=50" target="_blank">Comparar 50 SKU</a>
        <a class="btn" href="/wc-preview?limit=0" target="_blank">Comparar TODO</a>
      </div>
      <div class="card">
        <a class="btn" href="/">← Volver a Suite Ecommerce</a>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(body)


# gr.mount_gradio_app() registra el mount raíz antes de que server.py cargue.
# Starlette puede representar el path raíz como "" o "/". Lo mandamos al final
# para que /wc-health, /wc-preview e /inventory-sync se resuelvan primero.
_root_gradio_mounts = [
    route
    for route in fastapi_app.router.routes
    if isinstance(route, Mount) and getattr(route, "path", None) in {"", "/"}
]
if _root_gradio_mounts:
    fastapi_app.router.routes[:] = [
        route for route in fastapi_app.router.routes if route not in _root_gradio_mounts
    ] + _root_gradio_mounts
