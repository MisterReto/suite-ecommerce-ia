"""Bounded Loyverse REST client. Never retry writes or disclose remote bodies."""
import requests
import time


class LoyverseError(RuntimeError):
    pass


class LoyverseClient:
    BASE = 'https://api.loyverse.com/v1.0'

    def __init__(self, token, deadline=None):
        if not isinstance(token, str) or not 10 <= len(token.strip()) <= 4096 or any(c.isspace() for c in token.strip()):
            raise ValueError('Introduce un token de acceso válido de Loyverse.')
        self.token = token.strip()
        self.deadline = deadline or time.monotonic() + 120

    def request(self, method, path, **kwargs):
        if path not in {'/stores', '/items', '/inventory'}:
            raise ValueError('Operación no permitida.')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise LoyverseError('La consulta excedió el tiempo límite. Vuelve a comparar.')
        try:
            response = requests.request(method, self.BASE + path,
                headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'},
                timeout=(min(10, remaining), min(30, remaining)), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise LoyverseError('No se pudo confirmar la respuesta de Loyverse. Revisa antes de reintentar.') from None
        if response.status_code in (401, 403):
            raise LoyverseError('Loyverse rechazó el acceso. Revisa el token y sus permisos.')
        if response.status_code == 429:
            raise LoyverseError('Loyverse alcanzó su límite de solicitudes. Espera antes de reintentar.')
        if not 200 <= response.status_code < 300:
            raise LoyverseError('Loyverse no confirmó la operación. Revisa los datos y vuelve a comparar.')
        try:
            return response.json()
        except ValueError:
            raise LoyverseError('Respuesta inválida de Loyverse. Vuelve a comparar.') from None

    def list(self, resource, **params):
        key = 'inventory_levels' if resource == 'inventory' else resource
        rows, seen = [], set()
        for _ in range(200):
            data = self.request('GET', '/' + resource, params=dict(params, limit=250))
            page = data.get(key)
            if not isinstance(page, list):
                raise LoyverseError('Respuesta incompleta de Loyverse.')
            rows.extend(page)
            cursor = data.get('cursor')
            if not cursor:
                return rows
            if cursor in seen:
                break
            seen.add(cursor)
            params['cursor'] = cursor
        raise LoyverseError('El catálogo excede el límite de lectura o su paginación está incompleta.')

    def snapshot(self, store):
        stores = self.list('stores')
        if store not in {s['id'] for s in stores if not s.get('deleted_at')}:
            raise ValueError('Selecciona una sucursal activa de Loyverse.')
        return self.list('items'), self.list('inventory', store_ids=store)

    def set_stock(self, variant, store, value):
        return self.request('POST', '/inventory', json={'inventory_levels': [
            {'variant_id': variant, 'store_id': store, 'stock_after': value}]})

    def create_item(self, payload):
        if 'id' in payload or any('variant_id' in v for v in payload.get('variants', [])):
            raise ValueError('Esta operación solo permite crear productos nuevos.')
        return self.request('POST', '/items', json=payload)
