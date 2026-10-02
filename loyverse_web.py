"""Session-only Loyverse connection and explicit, one-use stock previews."""
import secrets
import time
from threading import RLock
from pathlib import Path
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
import app as runtime
from inventory_web import _context
from inventory_schema import MASTER_SHEET
from loyverse_client import LoyverseClient, LoyverseError
from loyverse_sync import plan_stock

LOCK = RLock()


def session(request):
    value = runtime.SESSIONS.get(request.cookies.get('session_id'))
    if not value or value.get('expires_at', 0) < time.time():
        raise PermissionError('Conecta Google Drive de nuevo.')
    return value


def client(value):
    return LoyverseClient(value.get('loyverse_token', ''))


def compare(request, value, store):
    _, book, sheets = _context(request)
    values = sheets.spreadsheets().values().get(
        spreadsheetId=book, range=f"'{MASTER_SHEET}'", valueRenderOption='UNFORMATTED_VALUE'
    ).execute().get('values', [])
    if not values:
        raise ValueError('El inventario de Drive está vacío.')
    headers = [str(v).strip() for v in values[0]]
    if any(headers.count(k) != 1 for k in ('sku', 'Existencias')):
        raise ValueError('Revisa las columnas SKU y Existencias del inventario.')
    rows = [dict(zip(headers, list(row) + [''] * max(0, len(headers)-len(row))))
            for row in values[1:] if any(str(v).strip() for v in row)]
    items, levels = client(value).snapshot(store)
    return plan_stock(rows, items, levels, store)


def _operate(request, action, data):
    value = session(request)
    if action == 'connect':
        api = LoyverseClient(data.get('token'))
        stores = api.list('stores')
        value['loyverse_token'] = api.token
        value.pop('loyverse_preview', None)
        return {'stores': [{'id': s['id'], 'name': s['name']} for s in stores if not s.get('deleted_at')]}
    if action == 'disconnect':
        value.pop('loyverse_token', None)
        value.pop('loyverse_preview', None)
        return {'ok': True}
    if action == 'preview':
        store = data.get('store')
        rows = compare(request, value, store)
        preview = {'id': secrets.token_urlsafe(24), 'expires': time.time() + 300, 'store': store, 'rows': rows}
        value['loyverse_preview'] = preview
        return {'id': preview['id'], 'rows': rows}
    if action != 'apply':
        raise ValueError('Operación no permitida.')
    if not LOCK.acquire(blocking=False):
        raise ValueError('Hay otra sincronización en curso. Espera y vuelve a comparar.')
    try:
        preview = value.pop('loyverse_preview', None)
        if not preview or preview['id'] != data.get('id') or preview['expires'] < time.time():
            raise ValueError('La revisión venció o ya fue utilizada. Vuelve a comparar.')
        selected = data.get('skus')
        if not isinstance(selected, list) or not selected or len(selected) > 20 or any(not isinstance(s, str) for s in selected) or len(set(selected)) != len(selected):
            raise ValueError('Selecciona entre 1 y 20 SKU únicos.')
        planned = {p['sku']: p for p in preview['rows'] if p['eligible']}
        current = {p['sku']: p for p in compare(request, value, preview['store'])}
        for sku in selected:
            if sku not in planned or planned[sku] != current.get(sku):
                raise ValueError('El inventario cambió o la selección no es válida. Vuelve a comparar.')
        completed = []
        api = client(value)
        for sku in selected:
            row = planned[sku]
            # A fresh stock read per write narrows the POS-sale race window.
            try:
                levels = api.list('inventory', store_ids=preview['store'], variant_ids=row['variant_id'])
            except LoyverseError:
                return {'completed': completed, 'uncertain': None, 'error': 'No se pudo consultar el siguiente SKU. Vuelve a comparar.'}
            found = [v for v in levels if v['variant_id'] == row['variant_id'] and v['store_id'] == preview['store']]
            if len(found) != 1 or found[0].get('in_stock') != row['loyverse'] or found[0].get('updated_at') != row['updated_at']:
                return {'completed': completed, 'error': 'El stock cambió durante la operación. Vuelve a comparar.', 'uncertain': None}
            try:
                result = api.set_stock(row['variant_id'], preview['store'], row['drive'])
                confirmed = [v for v in result.get('inventory_levels', []) if v.get('variant_id') == row['variant_id'] and v.get('store_id') == preview['store'] and v.get('in_stock') == row['drive']]
                if len(confirmed) != 1:
                    raise LoyverseError('La respuesta no confirmó el stock.')
            except LoyverseError:
                return {'completed': completed, 'uncertain': sku, 'error': 'No se confirmó este SKU. Revisa Loyverse y vuelve a comparar antes de reintentar.'}
            completed.append(sku)
        return {'completed': completed, 'uncertain': None}
    finally:
        LOCK.release()


def operate(request, action, data):
    if not LOCK.acquire(blocking=False):
        raise ValueError('Hay una operación de Loyverse en curso. Espera a que termine.')
    try:
        return _operate(request, action, data)
    finally:
        LOCK.release()


def register(app):
    @app.get('/loyverse', response_class=HTMLResponse)
    def page(request: Request):
        try:
            session(request)
        except PermissionError:
            return HTMLResponse('<h2>Conecta Google Drive en la Suite para acceder.</h2><a href="/">Volver</a>', status_code=401)
        return HTMLResponse(Path('static/loyverse.html').read_text())

    @app.post('/loyverse/{action}')
    async def endpoint(request: Request, action: str):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError('Solicitud inválida.')
            return await run_in_threadpool(operate, request, action, data)
        except PermissionError:
            return JSONResponse({'error': 'La sesión venció. Conecta Google Drive de nuevo.'}, status_code=401)
        except (ValueError, LoyverseError) as exc:
            return JSONResponse({'error': str(exc)}, status_code=400)
        except Exception:
            return JSONResponse({'error': 'No se pudo confirmar la operación. Revisa el estado y vuelve a comparar.'}, status_code=500)
