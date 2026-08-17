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
        raise RuntimeError("No encontré 'inventario_completo' en la carpeta configurada de Google Drive.")

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
        "woocommerce": _wc_config_status(),
        "duplicate_skus": sorted(duplicate_skus.keys()),
        "rows": previews,
    }


def _status_label(status: str) -> str:
    return {
        "in_sync": "✅ En sincronía",
        "inventory_mismatch": "🔴 Stock/precio distinto",
        "stock_unmanaged": "🟠 Stock no administrado",
        "content_difference": "🔵 Solo nombre distinto",
        "missing_in_woocommerce": "⚫ Falta en WooCommerce",
    }.get(status, status)


def _render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No hay filas en esta categoría.</p>"
    parts = [
        "<div style='overflow:auto'><table><thead><tr>",
        "<th>Estado</th><th>SKU</th><th>Producto</th><th>Marca</th><th>Tipo WC</th>",
        "<th>Stock Sheet</th><th>Stock WC</th><th>Gestiona stock</th>",
        "<th>Precio Sheet</th><th>Precio WC</th><th>Cambios</th>",
        "</tr></thead><tbody>",
    ]
    for row in rows:
        parts.append(
            "<tr>"
            f"<td>{html.escape(_status_label(row['status']))}</td>"
            f"<td><code>{html.escape(str(row.get('sku', '')))}</code></td>"
            f"<td>{html.escape(str(row.get('name', '')))}</td>"
            f"<td>{html.escape(str(row.get('brand', '')))}</td>"
            f"<td>{html.escape(str(row.get('entity_type') or ''))}</td>"
            f"<td>{html.escape(str(row.get('inventory_stock')))}</td>"
            f"<td>{html.escape(str(row.get('woocommerce_stock')))}</td>"
            f"<td>{'Sí' if row.get('manages_stock') else 'No'}</td>"
            f"<td>${html.escape(str(row.get('inventory_price')))}</td>"
            f"<td>${html.escape(str(row.get('woocommerce_price')))}</td>"
            f"<td>{html.escape(', '.join(row.get('changes') or []))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table></div>")
    return "".join(parts)


fastapi_app = legacy_app.fastapi_app


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


@fastapi_app.get("/inventory-sync", response_class=HTMLResponse)
def inventory_sync_dashboard(request: Request):
    cfg = _wc_config_status()
    session = _current_session(request)
    if not session:
        return HTMLResponse("<h2>Primero inicia sesión con Google Drive en la Suite.</h2><p><a href='/'>Volver</a></p>", status_code=401)

    try:
        _, rows = _read_master_inventory(session)
        payload = _build_preview(rows, limit=0)
        summary = payload["summary"]
        by_status: dict[str, list[dict[str, Any]]] = {}
        for row in payload["rows"]:
            by_status.setdefault(row["status"], []).append(row)

        cards = f"""
        <div class='grid'>
          <div class='metric'><b>{summary['total_inventory']}</b><span>SKU en Sheet</span></div>
          <div class='metric'><b>{summary['in_sync']}</b><span>En sincronía</span></div>
          <div class='metric'><b>{summary['inventory_mismatch']}</b><span>Stock/precio distinto</span></div>
          <div class='metric'><b>{summary['stock_unmanaged']}</b><span>Stock no administrado</span></div>
          <div class='metric'><b>{summary['content_difference']}</b><span>Solo nombre distinto</span></div>
          <div class='metric'><b>{summary['missing_in_woocommerce']}</b><span>Faltantes</span></div>
        </div>
        """
        duplicate_html = ", ".join(f"<code>{html.escape(s)}</code>" for s in payload["duplicate_skus"]) or "Ninguno"
        body = f"""
        <!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
        <title>Inventario ↔ WooCommerce</title>
        <style>
        body{{font-family:Arial,sans-serif;max-width:1500px;margin:30px auto;padding:0 20px;background:#f7f7f8;color:#1f2937}}
        .card,.metric{{background:white;border-radius:12px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}
        .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}}
        .metric b{{font-size:30px;display:block}} .metric span{{font-size:13px;color:#6b7280}}
        .card{{margin:16px 0}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid #e5e7eb;padding:8px;text-align:left;white-space:nowrap}} th{{position:sticky;top:0;background:#f3f4f6}}
        code{{background:#f3f4f6;padding:2px 5px;border-radius:4px}} a.btn{{display:inline-block;padding:10px 14px;background:#111827;color:#fff;border-radius:8px;text-decoration:none;margin-right:8px}}
        details{{margin:14px 0}} summary{{cursor:pointer;font-weight:bold;font-size:18px}}
        </style></head><body>
        <h1>📦 Inventario ↔ WooCommerce</h1>
        <div class='card'><b>🟢 Modo seguro: {html.escape(cfg['mode'])}</b><br>Tienda: <code>{html.escape(cfg['url'])}</code><br><br>
        <a class='btn' href='/'>← Suite</a><a class='btn' href='/wc-health' target='_blank'>Probar API</a><a class='btn' href='/wc-preview?limit=0' target='_blank'>JSON completo</a></div>
        {cards}
        <div class='card'><b>SKU duplicados en WooCommerce:</b> {duplicate_html}</div>
        <div class='card'>
          <details open><summary>🔴 Stock o precio distinto ({summary['inventory_mismatch']})</summary>{_render_table(by_status.get('inventory_mismatch', []))}</details>
          <details><summary>🟠 WooCommerce no administra stock ({summary['stock_unmanaged']})</summary>{_render_table(by_status.get('stock_unmanaged', []))}</details>
          <details><summary>⚫ Faltan en WooCommerce ({summary['missing_in_woocommerce']})</summary>{_render_table(by_status.get('missing_in_woocommerce', []))}</details>
          <details><summary>🔵 Solo cambia el nombre ({summary['content_difference']})</summary>{_render_table(by_status.get('content_difference', []))}</details>
          <details><summary>✅ En sincronía ({summary['in_sync']})</summary>{_render_table(by_status.get('in_sync', []))}</details>
        </div>
        <p><b>No hay botones de escritura en esta versión.</b> WC_WRITE_ENABLED debe permanecer en false.</p>
        </body></html>
        """
        return HTMLResponse(body)
    except Exception as exc:
        return HTMLResponse(f"<h2>Error</h2><pre>{html.escape(str(exc))}</pre>", status_code=500)


_root_gradio_mounts = [route for route in fastapi_app.router.routes if isinstance(route, Mount) and getattr(route, "path", None) in {"", "/"}]
if _root_gradio_mounts:
    fastapi_app.router.routes[:] = [route for route in fastapi_app.router.routes if route not in _root_gradio_mounts] + _root_gradio_mounts
