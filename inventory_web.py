"""UI web del inventario físico sobre la Suite existente.

Carga server.py (WooCommerce diagnóstico) y agrega un módulo de inventario real.
Todo movimiento escribe `Lista completa!Existencias` y `Movimientos Inventario`.
No escribe en WooCommerce.
"""
from __future__ import annotations

import html
import json
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount

import app as legacy_app
import server as integration_server
from inventory_operations import (
    MOVEMENT_TYPES,
    inventory_summary,
    inventory_table,
    movements_table,
    read_inventory,
    read_movements,
    register_movement,
    search_inventory,
)

fastapi_app = integration_server.fastapi_app


def _session(request: Request):
    sid = request.cookies.get("session_id")
    return legacy_app.SESSIONS.get(sid) if sid else None


def _context(request: Request):
    session = _session(request)
    if not session:
        raise PermissionError("Primero inicia sesión con Google Drive en la Suite.")
    spreadsheet_id, _ = integration_server._read_master_inventory(session)
    sheets = legacy_app._get_sheets_service(session)
    return session, spreadsheet_id, sheets


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def _render_inventory_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan='7'>No encontré productos.</td></tr>"
    out = []
    for row in rows:
        sku = html.escape(str(row.get("sku", "")))
        name = html.escape(str(row.get("nombre_producto", "")))
        brand = html.escape(str(row.get("Marca", "")))
        category = html.escape(str(row.get("categorias", "")))
        stock = int(row.get("Existencias", 0) or 0)
        price = _money(row.get("precio", 0))
        out.append(
            "<tr>"
            f"<td><button class='sku-btn' onclick='selectSku({json.dumps(str(row.get('sku', '')))})'>{sku}</button></td>"
            f"<td>{name}</td><td>{brand}</td><td>{category}</td>"
            f"<td class='num'><b>{stock}</b></td><td class='num'>{price}</td>"
            f"<td><a href='/inventory-manager?sku={sku}'>Historial</a></td>"
            "</tr>"
        )
    return "".join(out)


def _render_movements(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan='9'>Aún no hay movimientos registrados para este SKU.</td></tr>"
    out = []
    for r in rows:
        out.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('timestamp', '')))}</td>"
            f"<td><code>{html.escape(str(r.get('movement_id', '')))}</code></td>"
            f"<td>{html.escape(str(r.get('tipo', '')))}</td>"
            f"<td>{html.escape(str(r.get('cantidad', '')))}</td>"
            f"<td>{html.escape(str(r.get('stock_anterior', '')))}</td>"
            f"<td><b>{html.escape(str(r.get('stock_nuevo', '')))}</b></td>"
            f"<td>{html.escape(str(r.get('motivo', '')))}</td>"
            f"<td>{html.escape(str(r.get('referencia', '')))}</td>"
            f"<td>{html.escape(str(r.get('usuario', '')))}</td>"
            "</tr>"
        )
    return "".join(out)


@fastapi_app.get("/inventory-manager", response_class=HTMLResponse)
def inventory_manager(request: Request, q: str = "", sku: str = ""):
    try:
        session, spreadsheet_id, sheets = _context(request)
        rows = read_inventory(sheets, spreadsheet_id)
        filtered = search_inventory(rows, q, limit=150)
        summary = inventory_summary(rows)
        selected_sku = str(sku or "").strip()
        history = read_movements(sheets, spreadsheet_id, selected_sku, limit=50) if selected_sku else []
        movement_options = "".join(
            f"<option value='{html.escape(t)}'>{html.escape(t)}</option>" for t in MOVEMENT_TYPES
        )
        selected_title = html.escape(selected_sku) if selected_sku else "Selecciona un SKU"
        email = html.escape(str(session.get("email", "")))

        body = f"""<!doctype html>
<html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Inventario físico</title>
<style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}
.wrap{{max-width:1500px;margin:auto}} .card{{background:#fff;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.05)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}} .metric b{{font-size:30px;display:block}} .metric span{{color:#667085;font-size:13px}}
.metric{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}} input,select,textarea{{padding:10px;border:1px solid #cfd4dc;border-radius:8px;font:inherit;box-sizing:border-box}}
input[type=text]{{min-width:250px}} button,.btn{{border:0;border-radius:8px;background:#172033;color:#fff;padding:10px 14px;text-decoration:none;cursor:pointer;font:inherit}} .secondary{{background:#475467}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:9px;border-bottom:1px solid #e6e8ec;text-align:left;vertical-align:top}} th{{background:#f2f4f7;position:sticky;top:0}} .table-wrap{{max-height:520px;overflow:auto}} .num{{text-align:right}} .sku-btn{{background:#eef2ff;color:#27336b;padding:5px 8px}} code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}
.form-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}} .form-grid label{{display:flex;flex-direction:column;gap:5px;font-size:13px;font-weight:bold}} .notice{{padding:12px;border-radius:8px;background:#eefbf3;border:1px solid #86d7a2}} .error{{background:#fff1f1;border-color:#f1a3a3}}
</style></head><body><div class='wrap'>
<h1>📦 Inventario físico</h1>
<div class='card toolbar'><a class='btn secondary' href='/'>← Suite</a><a class='btn secondary' href='/inventory-sync'>WooCommerce</a><span>Sesión: <b>{email}</b></span></div>
<div class='grid'>
<div class='metric'><b>{summary['products']}</b><span>Productos</span></div><div class='metric'><b>{summary['units']}</b><span>Unidades registradas</span></div>
<div class='metric'><b>{summary['low_stock']}</b><span>Stock bajo (1–3)</span></div><div class='metric'><b>{summary['out_of_stock']}</b><span>Agotados</span></div>
<div class='metric'><b>{_money(summary['retail_value'])}</b><span>Valor a precio de venta</span></div>
</div>
<div id='msg'></div>
<div class='card'><h2>Registrar movimiento</h2><p>Para <b>Inventario inicial</b> y <b>Ajuste</b>, la cantidad representa el <u>stock final</u>. Para Entrada/Salida/Merma/Devolución representa unidades a sumar o restar.</p>
<div class='form-grid'>
<label>SKU<input id='m-sku' value='{html.escape(selected_sku)}' placeholder='Selecciona un SKU'></label>
<label>Movimiento<select id='m-type'>{movement_options}</select></label>
<label>Cantidad<input id='m-qty' type='number' min='0' step='1' value='0'></label>
<label>Referencia<input id='m-ref' placeholder='Factura, pedido, conteo...'></label>
<label>Motivo<input id='m-reason' placeholder='Compra, merma, corrección...'></label>
</div><br><button onclick='saveMovement()'>Guardar movimiento</button></div>
<div class='card'><h2>Catálogo</h2><form method='get' class='toolbar'><input name='q' value='{html.escape(q)}' placeholder='Buscar SKU, producto, marca o categoría'><button>Buscar</button><a class='btn secondary' href='/inventory-manager'>Limpiar</a></form><br>
<div class='table-wrap'><table><thead><tr><th>SKU</th><th>Producto</th><th>Marca</th><th>Categoría</th><th>Existencias</th><th>Precio</th><th></th></tr></thead><tbody>{_render_inventory_rows(filtered)}</tbody></table></div></div>
<div class='card'><h2>Historial — {selected_title}</h2><div class='table-wrap'><table><thead><tr><th>Fecha</th><th>ID</th><th>Tipo</th><th>Cantidad</th><th>Antes</th><th>Después</th><th>Motivo</th><th>Referencia</th><th>Usuario</th></tr></thead><tbody>{_render_movements(history)}</tbody></table></div></div>
</div>
<script>
function selectSku(sku){{ document.getElementById('m-sku').value=sku; window.history.replaceState(null,'','/inventory-manager?sku='+encodeURIComponent(sku)); }}
async function saveMovement(){{
 const msg=document.getElementById('msg'); msg.innerHTML='';
 const payload={{sku:document.getElementById('m-sku').value,movement_type:document.getElementById('m-type').value,quantity:document.getElementById('m-qty').value,reason:document.getElementById('m-reason').value,reference:document.getElementById('m-ref').value}};
 try{{ const r=await fetch('/inventory-movement',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}}); const data=await r.json(); if(!r.ok) throw new Error(data.error||'Error'); msg.innerHTML='<div class="notice">✅ '+data.message+'</div>'; setTimeout(()=>location.href='/inventory-manager?sku='+encodeURIComponent(payload.sku),700); }}catch(e){{ msg.innerHTML='<div class="notice error">❌ '+e.message+'</div>'; }}
}}
</script></body></html>"""
        return HTMLResponse(body)
    except PermissionError as exc:
        return HTMLResponse(f"<h2>{html.escape(str(exc))}</h2><a href='/'>Volver</a>", status_code=401)
    except Exception as exc:
        return HTMLResponse(f"<h2>Error</h2><pre>{html.escape(str(exc))}</pre>", status_code=500)


@fastapi_app.post("/inventory-movement")
async def inventory_movement(request: Request):
    try:
        session, spreadsheet_id, sheets = _context(request)
        payload = await request.json()
        result = register_movement(
            sheets,
            spreadsheet_id,
            sku=payload.get("sku", ""),
            movement_type=payload.get("movement_type", ""),
            quantity=payload.get("quantity", 0),
            reason=payload.get("reason", ""),
            reference=payload.get("reference", ""),
            user=session.get("email", ""),
        )
        return {
            "ok": True,
            "message": f"{result['sku']}: stock {result['old_stock']} → {result['new_stock']} ({result['movement_type']}).",
            "movement": result,
        }
    except PermissionError as exc:
        return JSONResponse(status_code=401, content={"ok": False, "error": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


# server.py ya reordena su mount raíz, pero acabamos de añadir rutas nuevas después.
# Lo mandamos al final nuevamente para que /inventory-* se resuelva antes de Gradio.
_root_mounts = [
    r for r in fastapi_app.router.routes
    if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}
]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
