"""UI de preview para publicar existencias de la Suite hacia WooCommerce.

Carga inventory_web.py y agrega una pantalla de revisión. Esta versión NO escribe
en WooCommerce aunque WC_WRITE_ENABLED sea true.
"""
from __future__ import annotations

import html
from collections import defaultdict

from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.routing import Mount

import inventory_web
from inventory_operations import read_inventory
from woocommerce_client import WooCommerceClient
from woocommerce_publish_preview import build_stock_publish_preview

fastapi_app = inventory_web.fastapi_app


def _label(status: str) -> str:
    return {
        "ready_product": "✅ Producto listo",
        "ready_variation": "✅ Variación lista",
        "missing": "⚫ SKU faltante",
        "duplicate": "🔴 SKU duplicado",
        "blocked_variable_parent": "🟠 Padre variable",
    }.get(status, status)


def _render(rows):
    if not rows:
        return "<p>No hay filas.</p>"
    out = ["<div class='table'><table><thead><tr><th>Estado</th><th>SKU</th><th>Producto</th><th>Stock a publicar</th><th>Destino</th><th>Razón</th></tr></thead><tbody>"]
    for row in rows:
        destination = ""
        if row.get("entity_type") == "variation":
            destination = f"Variación {row.get('product_id')} / padre {row.get('parent_product_id')}"
        elif row.get("product_id"):
            destination = f"Producto {row.get('product_id')}"
        out.append(
            "<tr>"
            f"<td>{html.escape(_label(row.get('status','')))}</td>"
            f"<td><code>{html.escape(str(row.get('sku','')))}</code></td>"
            f"<td>{html.escape(str(row.get('name','')))}</td>"
            f"<td><b>{html.escape(str(row.get('stock_to_publish',0)))}</b></td>"
            f"<td>{html.escape(destination)}</td>"
            f"<td>{html.escape(str(row.get('reason','')))}</td>"
            "</tr>"
        )
    out.append("</tbody></table></div>")
    return "".join(out)


@fastapi_app.get("/woocommerce-publish-preview", response_class=HTMLResponse)
def woocommerce_publish_preview(request: Request):
    try:
        session, spreadsheet_id, sheets = inventory_web._context(request)
        inventory = read_inventory(sheets, spreadsheet_id)
        client = WooCommerceClient()
        payload = build_stock_publish_preview(inventory, client)
        summary = payload["summary"]
        visibility = payload["visibility"]
        grouped = defaultdict(list)
        for row in payload["rows"]:
            grouped[row["status"]].append(row)

        if visibility["known"] and visibility["hide_out_of_stock"] is False:
            visibility_class = "ok"
            visibility_title = "✅ Los productos agotados deberían seguir visibles"
        elif visibility["known"] and visibility["hide_out_of_stock"] is True:
            visibility_class = "danger"
            visibility_title = "🛑 WooCommerce está ocultando productos agotados"
        else:
            visibility_class = "warn"
            visibility_title = "⚠️ No pude confirmar automáticamente la visibilidad de agotados"

        duplicate_html = ", ".join(f"<code>{html.escape(x)}</code>" for x in payload["duplicates"]) or "Ninguno"
        body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Preview publicación WooCommerce</title>
<style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1500px;margin:auto}}.card{{background:white;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.05)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.metric{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}.metric b{{font-size:28px;display:block}}.metric span{{font-size:13px;color:#667085}}.btn{{display:inline-block;background:#172033;color:white;padding:10px 14px;border-radius:8px;text-decoration:none;margin-right:8px}}.notice{{padding:16px;border-radius:10px;margin:14px 0}}.ok{{background:#eefbf3;border:1px solid #86d7a2}}.warn{{background:#fff7e8;border:1px solid #f5b84b}}.danger{{background:#fff0f0;border:1px solid #ef8e8e}}details{{margin:14px 0}}summary{{cursor:pointer;font-weight:bold;font-size:18px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e6e8ec;text-align:left}}th{{background:#f2f4f7;position:sticky;top:0}}.table{{max-height:560px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}
</style></head><body><div class='wrap'>
<h1>🚦 Preview de publicación a WooCommerce</h1>
<div class='card'><a class='btn' href='/inventory-manager'>← Inventario</a><a class='btn' href='/inventory-sync'>Diagnóstico WooCommerce</a><p><b>Esta pantalla es solo lectura.</b> No publica ni modifica productos.</p></div>
<div class='notice {visibility_class}'><b>{visibility_title}</b><br>{html.escape(str(visibility.get('warning') or ''))}<br>Configuración detectada: <code>{html.escape(str(visibility.get('setting_id') or 'desconocida'))}</code> = <code>{html.escape(str(visibility.get('raw_value')))}</code></div>
<div class='grid'>
<div class='metric'><b>{summary['total_inventory']}</b><span>SKU en la Suite</span></div>
<div class='metric'><b>{summary['ready_product']}</b><span>Productos simples listos</span></div>
<div class='metric'><b>{summary['ready_variation']}</b><span>Variaciones listas</span></div>
<div class='metric'><b>{summary['blocked_variable_parent']}</b><span>Padres variables bloqueados</span></div>
<div class='metric'><b>{summary['missing']}</b><span>SKU faltantes</span></div>
<div class='metric'><b>{summary['duplicate']}</b><span>SKU duplicados</span></div>
</div>
<div class='card'><b>Duplicados:</b> {duplicate_html}</div>
<div class='card'>
<details open><summary>✅ Productos simples listos ({summary['ready_product']})</summary>{_render(grouped['ready_product'])}</details>
<details><summary>✅ Variaciones listas ({summary['ready_variation']})</summary>{_render(grouped['ready_variation'])}</details>
<details><summary>🟠 Padres variables bloqueados ({summary['blocked_variable_parent']})</summary>{_render(grouped['blocked_variable_parent'])}</details>
<details><summary>⚫ SKU faltantes ({summary['missing']})</summary>{_render(grouped['missing'])}</details>
<details><summary>🔴 SKU duplicados ({summary['duplicate']})</summary>{_render(grouped['duplicate'])}</details>
</div>
<div class='card'><b>Siguiente paso:</b> solo cuando la visibilidad de agotados esté confirmada y resolvamos faltantes/duplicados, agregaremos un botón de publicación por lotes con confirmación explícita.</div>
</div></body></html>"""
        return HTMLResponse(body)
    except PermissionError as exc:
        return HTMLResponse(f"<h2>{html.escape(str(exc))}</h2><a href='/'>Volver</a>", status_code=401)
    except Exception as exc:
        return HTMLResponse(f"<h2>Error</h2><pre>{html.escape(str(exc))}</pre>", status_code=500)


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
