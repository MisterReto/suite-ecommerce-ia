"""Manual, read-only WooCommerce review within the inventory page."""
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount

import inventory_web
from app_security import public_error
from woocommerce_client import WooCommerceClient
from woocommerce_inventory import compare_product
from woocommerce_stock import stock_reading
from inventory_schema import is_variable_parent
from woocommerce_publish_preview import build_stock_publish_preview

fastapi_app = inventory_web.fastapi_app
_PREVIEW_LOCK = Lock()


@fastapi_app.post('/inventory-review')
def inventory_review(request: Request):
    session = inventory_web._session(request)
    if not session:
        return JSONResponse({'error': 'Conecta Google Drive primero.'}, status_code=401)
    if not _PREVIEW_LOCK.acquire(blocking=False):
        return JSONResponse({'error': 'Ya hay una revisión en curso.'}, status_code=429)
    try:
        _, inventory = inventory_web.integration_server._read_master_inventory(session)
        client = WooCommerceClient()
        # Download the catalog once for stock readiness and the comparison.
        catalog = client.catalog_by_sku(include_variations=True, force_refresh=True)
        stock = build_stock_publish_preview(inventory, client, catalog=catalog)
        stock_rows = {row['sku']: row for row in stock['rows']}
        rows, summary = [], {}
        for row in inventory:
            comparison = compare_product(row, catalog[0].get(row['sku'])).as_dict()
            if is_variable_parent(row):
                comparison.update(inventory_stock=None, woocommerce_stock=None, inventory_price=None, woocommerce_price=None)
            if row['sku'] in catalog[1]:
                comparison['status'] = 'duplicate'
            reading = stock_reading(catalog[0].get(row['sku']) or {})
            comparison.update(name=row.get('nombre_producto', ''), stock_preview=stock_rows[row['sku']],
                              stock_source=reading['source'], stock_parent_sku=reading['parent_sku'])
            summary[comparison['status']] = summary.get(comparison['status'], 0) + 1
            rows.append(comparison)
        return {'ok': True, 'rows': rows, 'summary': summary, 'visibility': stock['visibility'],
                'duplicates': stock['duplicates'],
                'source_stock': inventory_web.integration_server._stock_source_profile(inventory)}
    except PermissionError as exc:
        return JSONResponse({'error': public_error(exc)}, status_code=401)
    except Exception as exc:
        return JSONResponse({'error': public_error(exc)}, status_code=502)
    finally:
        _PREVIEW_LOCK.release()


@fastapi_app.api_route('/woocommerce-publish-preview', methods=['GET', 'POST'])
def woocommerce_publish_preview(request: Request):
    # Old bookmarks/forms return to the single page without starting a scan.
    return RedirectResponse('/inventory-hub#review', status_code=303)


@fastapi_app.post('/stock-preview-start')
@fastapi_app.get('/stock-preview-result')
def retired_stock_preview(request: Request):
    return JSONResponse({'error': 'La revisión en segundo plano está desactivada. Abre Inventario.'}, status_code=410)


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, 'path', None) in {'', '/'}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts

