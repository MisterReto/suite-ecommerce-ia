"""UI web del inventario físico sobre la Suite existente.

Carga server.py (WooCommerce diagnóstico) y agrega inventario real.
Todo movimiento escribe `Lista completa!Existencias` y `Movimientos Inventario`.
No escribe en WooCommerce.
"""
from __future__ import annotations

import html
import asyncio
from app_security import public_error
import json
import time
from urllib.parse import quote
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount

import app as legacy_app
import server as integration_server
from inventory_schema import is_variable_parent
from inventory_bulk import counted_initial_skus, register_initial_counts
from inventory_operations import (
    MOVEMENT_TYPES,
    inventory_summary,
    read_inventory,
    read_movements,
    register_movement,
    search_inventory,
)

fastapi_app = integration_server.fastapi_app
_RECENT_SUBMITS: dict[str, float] = {}


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


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


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


def _render_bulk_rows(rows: list[dict[str, Any]], counted: set[str]) -> str:
    out = []
    for row in rows:
        sku_raw = str(row.get("sku", ""))
        sku = html.escape(sku_raw)
        name = html.escape(str(row.get("nombre_producto", "")))
        brand = html.escape(str(row.get("Marca", "")))
        current = int(row.get("Existencias", 0) or 0)
        done = sku_raw in counted
        parent = is_variable_parent(row)
        category = html.escape(str(row.get("categorias", "")))
        current_text = "—" if parent else current
        price = "—" if parent else _money(row.get("precio", 0))
        count_input = "—" if parent else (
            f"<input aria-label='Conteo físico de {sku}' class='bulk-stock' data-sku='{sku}' "
            f"type='number' min='0' step='1' value='{current}'>"
        )
        out.append(
            "<tr>"
            f"<td><input aria-label='Seleccionar {sku}' class='bulk-check' type='checkbox' data-sku='{sku}' {'disabled' if parent else ''}></td>"
            f"<td><button class='sku-btn' data-history='{sku}'>{sku}</button></td>"
            f"<td>{name}</td><td>{brand}</td><td>{category}</td>"
            f"<td data-stock='{sku}'>{current_text}</td><td>{price}</td><td>{count_input}</td>"
            f"<td data-count-status='{sku}'>{'Portada sin stock propio' if parent else '✅ Ya contado' if done else 'Pendiente'}</td>"
            "</tr>"
        )
    return "".join(out)


def render_inventory(request: Request, q: str = "", sku: str = ""):
    try:
        session, spreadsheet_id, sheets = _context(request)
        rows = read_inventory(sheets, spreadsheet_id)
        filtered = search_inventory(rows, q, limit=500)
        summary = inventory_summary(rows)
        counted = counted_initial_skus(sheets, spreadsheet_id)
        pending = sum(not is_variable_parent(row) and str(row.get("sku", "")) not in counted for row in rows)
        selected_sku = str(sku or "").strip()
        history = read_movements(sheets, spreadsheet_id, selected_sku, limit=50) if selected_sku else []
        movement_options = "".join(
            f"<option value='{html.escape(t)}'>{html.escape(t)}</option>" for t in MOVEMENT_TYPES
        )
        body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>Suite e-commerce · Inventario</title>
<link rel='icon' href='/suite-static/rincon-logo.png'><link rel='stylesheet' href='/suite-static/inventory.css'>
<script src='/suite-static/inventory.js' defer></script></head><body><main class='wrap'>
<header><img src='/suite-static/rincon-logo.png' alt='El Rincón de Asia'><h1>Inventario</h1><a class='btn secondary' href='/'>← Suite</a></header>
<p>Sesión: <b>{html.escape(str(session.get("email", "")))}</b></p>
<div class='grid'>
<div class='metric'><b>{summary['products']}</b><span>Productos con stock propio</span></div>
<div class='metric'><b id='units'>{summary['units']}</b><span>Unidades registradas</span></div>
<div class='metric'><b id='low-stock'>{summary['low_stock']}</b><span>Stock bajo (1–3)</span></div>
<div class='metric'><b id='out-of-stock'>{summary['out_of_stock']}</b><span>Agotados</span></div>
<div class='metric'><b id='retail-value' data-value='{summary['retail_value']}'>{_money(summary['retail_value'])}</b><span>Valor a precio de venta</span></div>
</div><div id='msg' role='status' aria-live='polite'></div>
<section class='card' id='catalog'><h2>Catálogo y conteo físico</h2>
<p><b id='pending-count'>{pending}</b> SKU pendientes de conteo inicial. Escribe el stock físico final y selecciona únicamente los SKU que vas a guardar. Las portadas FULL no administran stock ni precio.</p>
<form method='get' action='/inventory-hub' class='toolbar'><input name='q' value='{html.escape(q)}' aria-label='Buscar productos' placeholder='SKU, producto, marca o categoría'><button>Buscar</button><a class='btn secondary' href='/inventory-hub'>Limpiar</a></form>
<p>Mostrando {len(filtered)} de {len(rows)} productos. Filtra por SKU si necesitas localizar otro producto.</p>
<div class='toolbar'><button id='bulk-btn' type='button'>Guardar conteos seleccionados en Drive</button><span id='selection-count' role='status'>0 seleccionados</span></div>
<div class='table-wrap'><table><thead><tr><th>Seleccionar</th><th>SKU / historial</th><th>Producto</th><th>Marca</th><th>Categoría</th><th>Existencias</th><th>Precio</th><th>Conteo físico final</th><th>Estado</th></tr></thead><tbody>{_render_bulk_rows(filtered, counted)}</tbody></table></div></section>
<section class='card' id='movement'><h2>Registrar movimiento</h2>
<p>Inventario inicial y Ajuste: stock final. Entrada, Salida, Merma y Devolución: unidades a sumar o restar.</p>
<div class='form-grid'>
<label>SKU<input id='m-sku' value='{html.escape(selected_sku)}' placeholder='Selecciona un SKU'></label>
<label>Movimiento<select id='m-type'>{movement_options}</select></label>
<label>Cantidad<input id='m-qty' type='number' min='0' step='1' value='0'></label>
<label>Referencia<input id='m-ref' placeholder='Factura, pedido, conteo…'></label>
<label>Motivo<input id='m-reason' placeholder='Compra, merma, corrección…'></label>
</div><p><button id='save-btn' type='button'>Guardar movimiento en Drive</button></p></section>
<section class='card' id='history'><h2>Historial — <span id='history-title'>{html.escape(selected_sku) if selected_sku else 'Selecciona un SKU'}</span></h2>
<div class='table-wrap'><table><thead><tr><th>Fecha</th><th>ID</th><th>Tipo</th><th>Cantidad</th><th>Antes</th><th>Después</th><th>Motivo</th><th>Referencia</th><th>Usuario</th></tr></thead><tbody id='history-rows'>{_render_movements(history)}</tbody></table></div></section>
<section class='card' id='review'><h2>Revisar Sheets y WooCommerce</h2>
<p>Compara nombres, existencias y precios; detecta faltantes, duplicados y visibilidad de agotados. La revisión se ejecuta solo al pulsar el botón y no modifica la tienda.</p>
<button id='review-btn' type='button'>Revisar sincronización y stock ahora</button>
<p id='review-status' role='status' aria-live='polite'>Aún no se ha consultado WooCommerce.</p><div id='review-summary' class='grid'></div>
<div class='table-wrap' id='review-table' hidden><table><thead><tr><th>SKU</th><th>Producto</th><th>Estado</th><th>Stock Drive</th><th>Stock tienda</th><th>Precio Drive</th><th>Precio tienda</th><th>Revisión de stock</th></tr></thead><tbody id='review-rows'></tbody></table></div>
<p><a class='btn secondary' href='/woocommerce-batch-sync'>Subir o actualizar productos</a></p></section>
</main></body></html>"""
        return HTMLResponse(body)
    except PermissionError as exc:
        return HTMLResponse(f"<h2>{html.escape(public_error(exc))}</h2><a href='/'>Volver</a>", status_code=401)
    except Exception as exc:
        return HTMLResponse(f"<h2>Error</h2><p>{html.escape(public_error(exc))}</p><a href='/inventory-hub'>Reintentar</a>", status_code=500)


@fastapi_app.get("/inventory-manager")
def inventory_manager(request: Request, q: str = "", sku: str = ""):
    return RedirectResponse("/inventory-hub?q=" + quote(q, safe="") + "&sku=" + quote(sku, safe=""), status_code=303)


@fastapi_app.get("/inventory-count")
def inventory_count(request: Request, q: str = ""):
    return RedirectResponse("/inventory-hub?" + "q=" + quote(q, safe="") + "#catalog", status_code=303)


@fastapi_app.get("/inventory-history")
def inventory_history(request: Request, sku: str = ""):
    try:
        _, spreadsheet_id, sheets = _context(request)
        selected = str(sku or "").strip()
        if not selected:
            raise ValueError("Selecciona un SKU.")
        return {"ok": True, "sku": selected, "rows": read_movements(sheets, spreadsheet_id, selected, limit=50)}
    except PermissionError as exc:
        return JSONResponse(status_code=401, content={"error": public_error(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": public_error(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": public_error(exc)})


@fastapi_app.post("/inventory-count-bulk")
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


@fastapi_app.post("/inventory-movement")
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


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
