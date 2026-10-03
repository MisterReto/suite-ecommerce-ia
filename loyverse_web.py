"""Session-only Loyverse connection and explicit, one-use stock previews."""
import secrets
from datetime import datetime, timezone, timedelta
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
from loyverse_sync import plan_catalog
import loyverse_jobs

LOCK = RLock()


def session(request):
    value = runtime.SESSIONS.get(request.cookies.get('session_id'))
    if not value or value.get('expires_at', 0) < time.time():
        raise PermissionError('Conecta Google Drive de nuevo.')
    return value


def client(value, deadline=None):
    return LoyverseClient(value.get('loyverse_token', ''), deadline=deadline)


def compare(request, value, store, bundle=None, api=None):
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
    api = api or client(value)
    stores = api.list('stores')
    if store not in {s['id'] for s in stores if not s.get('deleted_at')}:
        raise ValueError('La sucursal ya no está disponible.')
    items = api.list('items')
    levels = api.list('inventory', store_ids=store)
    if bundle is not None:
        bundle.update(rows=rows, items=items, levels=levels, stores=stores)
    return plan_catalog(rows, items, levels, store, stores)


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
    preview, selected = consume_preview(value, data)
    return execute_upload(request, value, preview, selected)


def consume_preview(value, data):
    preview = value.get('loyverse_preview')
    if not preview or preview['id'] != data.get('id') or preview['expires'] < time.time():
        raise ValueError('La revisión venció o ya fue utilizada. Vuelve a comparar.')
    selected = data.get('skus')
    if not isinstance(selected, list) or not selected or len(selected) > 20 or any(not isinstance(s, str) for s in selected) or len(set(selected)) != len(selected):
        raise ValueError('Selecciona entre 1 y 20 SKU únicos.')
    eligible = {p['sku'] for p in preview['rows'] if p['eligible']}
    if any(sku not in eligible for sku in selected):
        raise ValueError('Hay productos no disponibles en la selección. Vuelve a comparar.')
    value.pop('loyverse_preview', None)
    return preview, selected


def execute_upload(request, value, preview, selected, progress=lambda **fields: None):
    completed, created, attempted, current_sku = [], [], False, None
    deadline = time.monotonic() + 600
    # Updates after this overlapping watermark include catalog edits during the batch.
    since = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat().replace('+00:00', 'Z')
    planned = {p['sku']: p for p in preview['rows'] if p['eligible']}
    bundle = {}
    def result(error=None):
        return {'completed': completed, 'created': created, 'done': len(completed)+len(created),
                'uncertain': current_sku if attempted else None, 'error': error}
    try:
        api = client(value, deadline=deadline)
        progress(phase='Verificando Drive y Loyverse', current=None)
        fresh = {p['sku']: p for p in compare(request, value, preview['store'], bundle=bundle, api=api)}
        for sku in selected:
            if planned[sku] != fresh.get(sku):
                raise ValueError('El inventario cambió. Vuelve a comparar antes de enviar.')
        for current_sku in selected:
            attempted = False
            session(request)  # Do not start another write after session expiry.
            if time.monotonic() >= deadline:
                raise ValueError('La subida alcanzó su tiempo límite. Revisa los resultados y vuelve a comparar.')
            row = planned[current_sku]
            progress(current=current_sku, phase='Verificando producto')
            if row.get('action') == 'create':
                # Only recent catalog changes, instead of rereading all Drive/items/stock.
                changed = api.list('items', updated_at_min=since)
                if bundle:
                    item_map = {i['id']: i for i in bundle['items']}
                    item_map.update({i['id']: i for i in changed})
                    bundle['items'] = list(item_map.values())
                    fresh = {p['sku']: p for p in plan_catalog(**bundle, store=preview['store'])}
                    if fresh.get(current_sku) != row:
                        raise ValueError('El catálogo cambió. Vuelve a comparar antes de crear.')
                progress(phase='Enviando a Loyverse')
                attempted = True
                response = api.create_item(row['payload'])
                expected = {v['sku'] for v in row['payload']['variants']}
                actual = {v.get('sku') for v in response.get('variants', []) if v.get('variant_id')}
                if not response.get('id') or expected != actual:
                    raise LoyverseError('No se confirmó la creación completa.')
                created.append(current_sku)
                if bundle:
                    bundle['items'].append(response)
            else:
                levels = api.list('inventory', store_ids=preview['store'], variant_ids=row['variant_id'])
                found = [v for v in levels if v['variant_id'] == row['variant_id'] and v['store_id'] == preview['store']]
                if len(found) != 1 or found[0].get('in_stock') != row['loyverse'] or found[0].get('updated_at') != row['updated_at']:
                    raise ValueError('El stock cambió durante la subida. Vuelve a comparar.')
                progress(phase='Enviando a Loyverse')
                attempted = True
                response = api.set_stock(row['variant_id'], preview['store'], row['drive'])
                confirmed = [v for v in response.get('inventory_levels', []) if v.get('variant_id') == row['variant_id'] and v.get('store_id') == preview['store'] and v.get('in_stock') == row['drive']]
                if len(confirmed) != 1:
                    raise LoyverseError('La respuesta no confirmó el stock.')
                completed.append(current_sku)
            attempted = False
            progress(**result(), phase='Producto confirmado')
        return result()
    except (ValueError, LoyverseError) as exc:
        return result(str(exc) + ' Revisa los resultados antes de reintentar.')
    except Exception:
        return result('No se pudo confirmar la operación. Revisa Loyverse antes de reintentar.')


def start_upload(request, data):
    value = session(request)
    previous = loyverse_jobs.status(value)
    if previous and previous['preview_id'] == data.get('id'):
        return previous
    if not LOCK.acquire(blocking=False):
        raise ValueError('Hay otra operación de Loyverse en curso. Espera antes de enviar.')
    try:
        previous = loyverse_jobs.status(value)
        if previous and previous['preview_id'] == data.get('id'):
            return previous
        if previous and previous['state'] in loyverse_jobs.ACTIVE_STATES:
            raise ValueError('Hay una subida en curso. Consulta su progreso.')
        preview, selected = consume_preview(value, data)
        def target(progress):
            with LOCK:
                return execute_upload(request, value, preview, selected, progress)
        return loyverse_jobs.launch(value, preview['id'], len(selected), target)
    finally:
        LOCK.release()


def operate(request, action, data):
    if not LOCK.acquire(blocking=False):
        raise ValueError('Hay una operación de Loyverse en curso. Espera a que termine.')
    try:
        if (loyverse_jobs.status(session(request)) or {}).get('state') in loyverse_jobs.ACTIVE_STATES:
            raise ValueError('Hay una subida en curso. Consulta su progreso.')
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

    @app.get('/loyverse-upload-status')
    def upload_status(request: Request, job_id: str = ''):
        try:
            value = session(request)
            job = loyverse_jobs.status(value, job_id)
            if job_id and not job:
                return JSONResponse({'error': 'La subida no está disponible en esta sesión. Revisa Loyverse y vuelve a comparar.'}, status_code=404)
            return JSONResponse({'job': job}, headers={'Cache-Control': 'no-store'})
        except PermissionError:
            return JSONResponse({'error': 'La sesión venció o el servicio reinició. Revisa Loyverse antes de volver a enviar.'}, status_code=401)

    @app.post('/loyverse/{action}')
    async def endpoint(request: Request, action: str):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError('Solicitud inválida.')
            if action == 'apply':
                job = await run_in_threadpool(start_upload, request, data)
                return JSONResponse(job, status_code=202)
            return await run_in_threadpool(operate, request, action, data)
        except PermissionError:
            return JSONResponse({'error': 'La sesión venció. Conecta Google Drive de nuevo.'}, status_code=401)
        except (ValueError, LoyverseError) as exc:
            return JSONResponse({'error': str(exc)}, status_code=400)
        except Exception:
            return JSONResponse({'error': 'No se pudo confirmar la operación. Revisa el estado y vuelve a comparar.'}, status_code=500)
